import time
from multiprocessing import Process, Queue, current_process
from sys import platform

from .StatCollector import StatCollector
from .Stats import Stats
from .utils import format_size


class Monitoring:
    def __init__(self, find_children: bool = False):
        self.pid: int = current_process().pid  # type: ignore
        self.find_children = find_children
        self.stat_collector = StatCollector(self.pid)
        self.stats_per_pid = {}
        self.formated_stats: Stats = Stats()

    @staticmethod
    def has_process_crashed(queue):
        while not queue.empty():
            if not queue.get():
                return True
        return False

    def take_snapshot(self):
        self.pre_success_queue = Queue()
        self.pre_data_queue = Queue()

        # Take a snapshot of RAM and IO stats for the process and its children
        self.take_snapshot_process = Process(
            target=self.collect_snapshot_stats, args=(self.pre_data_queue, self.pre_success_queue)
        )
        self.take_snapshot_process.start()

        self.take_snapshot_process.join()  # Ensure process termination
        has_process_crashed = self.has_process_crashed(self.pre_success_queue)
        if has_process_crashed:
            print("Process snapshot has crashed")
            self.take_snapshot_process.terminate()

        raw_snapshot_stats = self.pre_data_queue.get()
        self.stats_per_pid = self.stat_collector.calculate_statistics_from_data(raw_snapshot_stats)

    def collect_snapshot_stats(self, pre_data_queue, success_queue):
        refresh_rate: float = 0.0
        stats = {}

        cpu_memory_stats = self.stat_collector.collect_cpu_ram_stats(
            stats, self.find_children, refresh_rate, success_queue
        )

        stats = self.stat_collector.collect_io_counters(cpu_memory_stats, self.find_children, success_queue)

        pre_data_queue.put(stats)

    def start_monitoring(self):
        self.stop_queue = Queue()
        self.data_pool_queue = Queue()
        self.success_queue = Queue()
        self.pooling_raw_stats: dict | None = None

        # Start the monitoring process
        self.pooling_process = Process(
            target=self.pool_stats, args=(self.data_pool_queue, self.stop_queue, self.success_queue)
        )
        self.pooling_process.start()

    def stop_monitoring(self):
        # Send a signal to stop the pooling process
        self.stop_queue.put("STOP")

        self.pooling_process.join()  # type: ignore
        has_process_crashed = self.has_process_crashed(self.success_queue)
        if has_process_crashed:
            print("Process pooling has crashed")
            self.pooling_process.terminate()  # type: ignore

        pooling_raw_stats = self.data_pool_queue.get()
        self.stats_per_pid = self.stat_collector.calculate_statistics_from_data(pooling_raw_stats)

    def pool_stats(self, data_pool_queue, stop_queue, success_queue):
        refresh_rate: float = 0.1  # Initial refresh rate
        max_refresh_rate: int = 5  # Maximum refresh rate
        time_elapsed: float = 0.0
        stats = {}

        while True:

            stats = self.stat_collector.collect_cpu_ram_stats(stats, self.find_children, refresh_rate, success_queue)
            if not stop_queue.empty():
                message = stop_queue.get()
                if message == "STOP":
                    stats = self.stat_collector.collect_io_counters(stats, self.find_children, success_queue)
                    data_pool_queue.put(stats)
                    break
            time.sleep(refresh_rate)
            time_elapsed += refresh_rate
            if time_elapsed > 10:
                if refresh_rate < max_refresh_rate:
                    refresh_rate = min(refresh_rate * 2, max_refresh_rate)
                    # Double the refresh rate, but do not exceed max_refresh_rate
                time_elapsed = 0.0

    def calculate_delta(self, other):
        subtracted_stats = self.stat_collector.subtract_stats(self.stats_per_pid, other.stats_per_pid)
        self.formated_stats = self.stat_collector.get_final_stats(subtracted_stats)

    def get_data(self):
        return self.formated_stats

    def print(self, verbose, func_name, args, kwargs) -> None:
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
        data = self.formated_stats
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
                print(f"IO bytes: {format_size(data.read_bytes)}.")
                print(f"IO writes count: {data.write_count}.")
                print(f"IO bytes: {format_size(data.write_bytes)}.")
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
