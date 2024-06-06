import time
from sys import platform
from typing import Dict, Self

from multiprocess import Process, Queue, current_process  # type: ignore

from .StatCollector import StatCollector
from .Stats import RawStats, Stats
from .utils import format_size


class Monitoring:
    def __init__(self, find_children: bool = False):
        """
        Initializes a new instance of the Monitoring class.

        Args:
            find_children (bool, optional): If True, the monitoring process will also monitor child processes spawned by the main process. Defaults to False.

        Returns:
            None
        """
        self.pid: int = current_process().pid  # type: ignore
        self.find_children: bool = find_children
        self.stat_collector: StatCollector = StatCollector(self.pid)
        self.stats_per_pid: Dict[int, Stats] = {}
        self.formated_stats: Stats = Stats()

    @staticmethod
    def has_process_crashed(queue: Queue) -> bool:
        """
        Checks if the process has crashed based on the given queue.

        Args:
            queue (Queue): The queue containing the process status.

        Returns:
            bool: True if the process has crashed, False otherwise.
        """
        while not queue.empty():
            if not queue.get():
                return True
        return False

    def take_snapshot(self):
        """
        Takes a snapshot of RAM and IO stats for the process and its children.
        Saves the result in `self.stats_per_pid` in the form of Dict[int, Stats].
        """

        self.pre_success_queue = Queue()
        self.pre_data_queue = Queue()

        # Take a snapshot of RAM and IO stats for the process and its children
        try:
            take_snapshot_process: Process = Process(target=self.collect_snapshot_stats, args=())
            take_snapshot_process.start()
            take_snapshot_process.join()  # Ensure process termination
            has_process_crashed: bool = self.has_process_crashed(self.pre_success_queue)
            if has_process_crashed:
                print("Process snapshot has crashed")
                take_snapshot_process.terminate()
            raw_snapshot_stats: Dict[int, RawStats] = self.pre_data_queue.get()

        except Exception:
            raw_snapshot_stats = {}  # Avoid hanging the process if something goes wrong

        self.stats_per_pid: Dict[int, Stats] = self.stat_collector.calculate_statistics_from_data(raw_snapshot_stats)

        # Clear queues
        self.pre_data_queue.close()
        self.pre_success_queue.close()
        delattr(self, "pre_data_queue")
        delattr(self, "pre_success_queue")

    def collect_snapshot_stats(self):
        """
        Collects CPU and RAM statistics for the process and its children, and IO counters.
        The result is added to the queue.
        It uses queues to pass the data:
            pre_data_queue (Queue): A queue to store the collected statistics.
            success_queue (Queue): A queue to communicate success or failure.
        """
        refresh_rate: float = 0.0
        raw_stats: Dict[int, RawStats] = {}

        cpu_memory_stats = self.stat_collector.collect_cpu_ram_stats(
            raw_stats, self.find_children, refresh_rate, self.pre_success_queue
        )

        raw_stats = self.stat_collector.collect_io_counters(
            cpu_memory_stats, self.find_children, self.pre_success_queue
        )

        self.pre_data_queue.put(raw_stats)

    def start_monitoring(self):
        """
        Initializes the monitoring process by creating queues and starting the pooling process.
        This function initializes the monitoring process by creating the necessary queues for communication between the main process and the pooling process.
        """

        self.stop_queue = Queue()
        self.data_pool_queue = Queue()
        self.success_queue = Queue()
        self.pooling_raw_stats: Dict | None = None

        # Start the monitoring process
        self.pooling_process = Process(target=self.pool_stats, args=())
        self.pooling_process.start()

    def stop_monitoring(self):
        """
        Stops the monitoring process by sending a signal to stop the pooling process.
        This function sends a signal to stop the pooling process by putting the string "STOP" into the `stop_queue`.
        It then waits for the pooling process to terminate using the `join()` method.
        If the pooling process has crashed, it prints a message and terminates the process using the `terminate()` method.
        After that, it retrieves the raw statistics from the `data_pool_queue` and calculates the statistics per PID using the `calculate_statistics_from_data()` method of the `stat_collector` object.
        The object stats_per_pid is a dict of Stats objects, where the keys are the PIDs and the values are the corresponding Stats objects.
        """
        # Send a signal to stop the pooling process
        self.stop_queue.put("STOP")
        self.pooling_process.join()  # type: ignore
        has_process_crashed = self.has_process_crashed(self.success_queue)
        if has_process_crashed:
            print("Process pooling has crashed")
            self.pooling_process.terminate()  # type: ignore

        pooling_raw_stats: Dict[int, RawStats] = self.data_pool_queue.get()

        self.stats_per_pid = self.stat_collector.calculate_statistics_from_data(pooling_raw_stats)

        # Clean queues and process
        self.stop_queue.close()
        self.data_pool_queue.close()
        self.success_queue.close()
        delattr(self, "stop_queue")
        delattr(self, "data_pool_queue")
        delattr(self, "success_queue")
        delattr(self, "pooling_process")

    def pool_stats(self):
        """
        Collects statistics about CPU and RAM usage and IO counters for the process and its children.
        It uses queues to pass the data:
            data_pool_queue (Queue): A queue to store the collected statistics as a dict of RawStats.
            stop_queue (Queue): A queue to receive stop signals.
            success_queue (Queue): A queue to communicate success or failure.
        """
        refresh_rate: float = 0.1  # Initial refresh rate
        max_refresh_rate: int = 5  # Maximum refresh rate
        time_elapsed: float = 0.0
        stats: Dict[int, RawStats] = {}

        while True:

            stats = self.stat_collector.collect_cpu_ram_stats(
                stats, self.find_children, refresh_rate, self.success_queue
            )

            # This call will help if find children = True and some of them die before the STOP signal is received so IO counters for dead processes will not be collected.
            stats = self.stat_collector.collect_io_counters(stats, self.find_children, self.success_queue)
            if not self.stop_queue.empty():
                message = self.stop_queue.get()
                if message == "STOP":
                    stats = self.stat_collector.collect_io_counters(stats, self.find_children, self.success_queue)
                    self.data_pool_queue.put(stats)
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
        Calculate the difference between the current instance's stats_per_pid and another instance's stats_per_pid.

        Args:
            other (Self): The other instance to compare stats_per_pid with.
        """
        subtracted_stats: Dict[int, Stats] = self.stat_collector.subtract_stats(self.stats_per_pid, other.stats_per_pid)
        self.formated_stats: Stats = self.stat_collector.get_final_stats(subtracted_stats)

    def get_data(self):
        """
        Retrieves the formatted statistics from the `formated_stats` attribute of the current instance.
        Returns:
            The formatted statistics as a `Stats` object.
        """
        return self.formated_stats

    def print(self, verbose: bool, func_name: str, args: tuple, kwargs: dict) -> None:
        """
        Prints the metrit data for a given function.

        Parameters:
            verbose (bool): If True, prints detailed information about the metrit data. If False, prints a concise summary.
            func_name (str): The name of the function.
            args (tuple): The positional arguments passed to the function.
            kwargs (dict): The keyword arguments passed to the function.

        Returns:
            None
        """
        data: Stats = self.formated_stats
        if verbose:
            print("*" * 5, f"metrit data for function {func_name}:", "*" * 5)
            print(f"\tArgs: {args}.")
            print(f"\tKwargs: {kwargs}.")
            print(f"Maximum CPU usage: {data.cpu_percentage_max:.2f}%.")
            print(f"Average CPU usage: {data.cpu_percentage_avg:.2f}%.")
            print(f"Average memory usage: {data.memory_percentage_avg:.2f}%.")
            print(f"Maximum RSS memory usage: {format_size(data.rss_bytes_max)}.")
            print(f"Average RSS memory usage: {format_size(data.rss_bytes_avg)}.")
            print(f"Maximum VMS memory usage: {format_size(data.vms_bytes_max)}.")
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
                output_format = "Function {:30} {:>8} avg of memory {:>8.2f}% avg of CPU {:>8} IO reads {:>8} IO writes"
                output = output_format.format(
                    func_name,
                    format_size(data.rss_bytes_avg),
                    data.cpu_percentage_avg,
                    format_size(data.read_bytes),
                    format_size(data.write_bytes),
                )
            else:
                output_format = "Function {:30} {:>8} avg of memory {:>8.2f}% avg of CPU"
                output = output_format.format(func_name, format_size(data.rss_bytes_avg), data.cpu_percentage_avg)
            print(output)
