import logging
import time
from sys import platform
from typing import Dict, Self

import psutil
from multiprocess import Process, Queue, current_process  # type: ignore

from .StatCollector import StatCollector
from .Stats import RawStats, Stats
from .utils import format_size

logger = logging.getLogger("metrit")

# Safety nets so a crashed helper process can never hang the caller.
# The snapshot is a quick one-off collection, so it should never take this long.
_SNAPSHOT_JOIN_TIMEOUT: float = 30.0
# After the STOP signal the pooler should exit within one refresh cycle (<=5s).
_POOL_JOIN_TIMEOUT: float = 10.0
# Maximum time to wait for data once the producing process has already stopped.
_QUEUE_GET_TIMEOUT: float = 5.0
# Maximum time to wait for the pooler to be ready (spawning a process can be slow,
# especially on Windows). If it is exceeded we proceed anyway (best effort).
_POOL_READY_TIMEOUT: float = 30.0


class Monitoring:
    def __init__(self, find_children: bool = False):
        """
        Initializes a new instance of the Monitoring class.

        Args:
            find_children (bool, optional): If True, the monitoring will also measure child
                processes spawned by the target process. Defaults to False.
        """
        self.pid: int = current_process().pid  # type: ignore
        self.find_children: bool = find_children
        self.stat_collector: StatCollector = StatCollector(self.pid)
        self.formated_stats: Stats = Stats()
        # Baseline (pre-run) and pooled (during-run) data, combined by `calculate_delta`.
        self.baseline_totals: RawStats = RawStats()
        self.baseline_io: Dict[int, RawStats] = {}
        self.pool_totals: RawStats = RawStats()
        self.pool_io: Dict[int, RawStats] = {}

    @staticmethod
    def has_process_crashed(queue: Queue) -> bool:
        """
        Checks if the process has crashed based on the given queue.
        Returns True if any collected status is a failure.
        """
        while not queue.empty():
            if not queue.get():
                return True
        return False

    def take_snapshot(self):
        """
        Records a baseline snapshot of the target process' resources (and children).
        The result is stored in `self.baseline_io` and `self.baseline_totals`.
        """
        self.pre_success_queue = Queue()
        self.pre_data_queue = Queue()

        baseline_io: Dict[int, RawStats] = {}
        baseline_totals = RawStats()
        try:
            take_snapshot_process: Process = Process(target=self.collect_snapshot_stats, args=())
            take_snapshot_process.start()
            take_snapshot_process.join(_SNAPSHOT_JOIN_TIMEOUT)  # Ensure process termination
            if take_snapshot_process.is_alive():
                logger.warning("Process snapshot took too long, terminating it")
                take_snapshot_process.terminate()
                take_snapshot_process.join(_POOL_JOIN_TIMEOUT)

            has_process_crashed: bool = self.has_process_crashed(self.pre_success_queue)
            if has_process_crashed:
                logger.warning("Process snapshot has crashed")
            else:
                baseline_io, baseline_totals = self.pre_data_queue.get(timeout=_QUEUE_GET_TIMEOUT)
        except Exception:
            baseline_io, baseline_totals = {}, RawStats()  # Avoid hanging if something goes wrong

        self.baseline_io = baseline_io
        self.baseline_totals = baseline_totals

        # Clear queues
        self.pre_data_queue.close()
        self.pre_success_queue.close()
        delattr(self, "pre_data_queue")
        delattr(self, "pre_success_queue")

    def collect_snapshot_stats(self):
        """
        Collects a baseline snapshot of CPU/RAM and IO for the target and its children, and
        puts ``(per_pid_raw, totals)`` on the queue.
        """
        raw_stats: Dict[int, RawStats] = {}
        totals = RawStats()

        raw_stats, totals = self.stat_collector.collect_cpu_ram_stats(
            raw_stats, totals, self.find_children, self.pre_success_queue
        )
        raw_stats = self.stat_collector.collect_io_counters(raw_stats, self.find_children, self.pre_success_queue)

        self.pre_data_queue.put((raw_stats, totals))

    def start_monitoring(self):
        """
        Initializes the monitoring process by creating queues and starting the pooling process.
        """
        self.stop_queue = Queue()
        self.data_pool_queue = Queue()
        self.success_queue = Queue()
        self.ready_queue = Queue()

        # Start the monitoring process
        self.pooling_process = Process(target=self.pool_stats, args=())
        self.pooling_process.start()

        # Wait until the pooler has primed its counters, so the function under test does
        # not start before monitoring is actually sampling. Spawning can be slow on
        # Windows/macOS (spawn), so this is bounded and best-effort.
        try:
            self.ready_queue.get(timeout=_POOL_READY_TIMEOUT)
        except Exception:
            logger.warning("Monitoring pooler did not signal readiness in time")

    def stop_monitoring(self):
        """
        Stops the pooling process and retrieves the pooled data.

        Sends a STOP signal, waits for the pooler with a timeout, and reads the pooled data
        with a timeout so a crashed pooler can never block the caller. The result is stored in
        `self.pool_io` and `self.pool_totals`.
        """
        # Send a signal to stop the pooling process
        self.stop_queue.put("STOP")
        self.pooling_process.join(_POOL_JOIN_TIMEOUT)  # type: ignore
        if self.pooling_process.is_alive():  # type: ignore
            logger.warning("Process pooling did not stop in time, terminating it")
            self.pooling_process.terminate()  # type: ignore
            self.pooling_process.join(_POOL_JOIN_TIMEOUT)  # type: ignore

        has_process_crashed = self.has_process_crashed(self.success_queue)
        if has_process_crashed:
            logger.warning("Process pooling has crashed")

        # Never block forever: if the pooler crashed it may not have produced data.
        try:
            pool_io, pool_totals = self.data_pool_queue.get(timeout=_QUEUE_GET_TIMEOUT)
        except Exception:
            pool_io, pool_totals = {}, RawStats()

        self.pool_io = pool_io
        self.pool_totals = pool_totals

        # Clean queues and process
        self.stop_queue.close()
        self.data_pool_queue.close()
        self.success_queue.close()
        if hasattr(self, "ready_queue"):
            self.ready_queue.close()
            delattr(self, "ready_queue")
        delattr(self, "stop_queue")
        delattr(self, "data_pool_queue")
        delattr(self, "success_queue")
        delattr(self, "pooling_process")

    def pool_stats(self):
        """
        Samples the target (and children) on a fixed cadence until the STOP signal arrives.

        CPU is sampled non-blocking on cached Process objects, so each sample covers the time
        since the previous one (the cadence). The per-tick totals are summed across processes
        so the final aggregate is coherent. The cadence adapts from 0.1s up to 5s.
        """
        refresh_rate: float = 0.1  # Initial refresh rate
        max_refresh_rate: int = 5  # Maximum refresh rate
        time_elapsed: float = 0.0
        stats: Dict[int, RawStats] = {}
        totals = RawStats()

        # Prime CPU counters, then let the caller know monitoring is active before the
        # function under test starts.
        self.stat_collector.prime(self.find_children)
        self.ready_queue.put(True)
        time.sleep(refresh_rate)

        while True:

            # If the monitored process died without a STOP signal (hard crash), stop
            # pooling instead of lingering forever as an orphaned process.
            if not psutil.pid_exists(self.pid):
                break

            stats, totals = self.stat_collector.collect_cpu_ram_stats(
                stats, totals, self.find_children, self.success_queue
            )

            # Refresh IO counters on every iteration so children that die before the STOP
            # signal are still captured.
            stats = self.stat_collector.collect_io_counters(stats, self.find_children, self.success_queue)
            if not self.stop_queue.empty():
                message = self.stop_queue.get()
                if message == "STOP":
                    stats = self.stat_collector.collect_io_counters(stats, self.find_children, self.success_queue)
                    self.data_pool_queue.put((stats, totals))
                    break
            time.sleep(refresh_rate)
            time_elapsed += refresh_rate
            if time_elapsed > 10:
                if refresh_rate < max_refresh_rate:
                    refresh_rate = min(refresh_rate * 2, max_refresh_rate)
                    # Double the refresh rate, but do not exceed max_refresh_rate
                time_elapsed = 0.0

    def calculate_delta(self, other: Self):
        """
        Combines this (pooled) instance with the baseline instance into `self.formated_stats`.
        """
        self.formated_stats = self.stat_collector.finalize(
            self.pool_totals, other.baseline_totals, self.pool_io, other.baseline_io
        )

    def get_data(self):
        """
        Returns the formatted statistics as a `Stats` object.
        """
        return self.formated_stats

    def print(self, verbose: bool, func_name: str, args: tuple, kwargs: dict) -> None:
        """
        Prints the metrit data for a given function.

        Parameters:
            verbose (bool): If True, prints detailed information; otherwise a concise summary.
            func_name (str): The name of the function.
            args (tuple): The positional arguments passed to the function.
            kwargs (dict): The keyword arguments passed to the function.
        """
        data: Stats = self.formated_stats
        if verbose:
            print("*" * 5, f"metrit data for function {func_name}:", "*" * 5)
            print(f"\tArgs: {args}.")
            print(f"\tKwargs: {kwargs}.")
            print(f"Maximum CPU usage: {data.cpu_percentage_max:.2f}%.")
            print(f"Average CPU usage: {data.cpu_percentage_avg:.2f}%.")
            print(f"Peak memory usage: {data.memory_percentage_max:.2f}%.")
            print(f"Average memory usage: {data.memory_percentage_avg:.2f}%.")
            print(f"Peak RSS memory usage: {format_size(data.rss_bytes_max)}.")
            print(f"RSS memory growth: {format_size(data.rss_bytes_growth)}.")
            print(f"Average RSS memory usage: {format_size(data.rss_bytes_avg)}.")
            print(f"Peak VMS memory usage: {format_size(data.vms_bytes_max)}.")
            print(f"VMS memory growth: {format_size(data.vms_bytes_growth)}.")
            print(f"Average VMS memory usage: {format_size(data.vms_bytes_avg)}.")

            if platform != "darwin":
                print(f"IO read count: {data.read_count}.")
                print(f"IO writes count: {data.write_count}.")
                print(f"IO read bytes: {format_size(data.read_bytes)}.")
                print(f"IO write bytes: {format_size(data.write_bytes)}.")
            print("*" * 5, "End of metrit data.", "*" * 5)
        else:
            func_name_spacing = 30
            func_name = f"'{func_name}'"
            if len(func_name) > func_name_spacing:
                func_name = func_name[: func_name_spacing - 4] + "..." + "'"
            if platform != "darwin":
                output_format = "Function {:30} {:>8} peak memory {:>8.2f}% avg of CPU {:>8} IO reads {:>8} IO writes"
                output = output_format.format(
                    func_name,
                    format_size(data.rss_bytes_max),
                    data.cpu_percentage_avg,
                    format_size(data.read_bytes),
                    format_size(data.write_bytes),
                )
            else:
                output_format = "Function {:30} {:>8} peak memory {:>8.2f}% avg of CPU"
                output = output_format.format(func_name, format_size(data.rss_bytes_max), data.cpu_percentage_avg)
            print(output)
