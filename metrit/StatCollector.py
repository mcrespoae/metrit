from statistics import mean
from sys import platform
from typing import Dict, Tuple

import psutil
from multiprocess import Queue, current_process  # type: ignore

from .Stats import RawStats, Stats


class StatCollector:
    def __init__(self, pid):
        """
        Initializes a new instance of the StatCollector class.
        Args:
            pid (int): The process ID of the process to collect stats for.
        Returns:
            None
        """
        self.pid = pid
        self.stats = {}

    def collect_cpu_ram_stats(
        self, stats: Dict, find_children: bool, refresh_rate: float, sucesss_queue: Queue
    ) -> Dict[int, RawStats]:
        """
        Collects current CPU and RAM stats for the process and its children.

        Args:
            stats (Dict): A dictionary to store the collected stats as {pid: RawStats}.
            find_children (bool): Whether to collect stats for the process's children.
            refresh_rate (float): The refresh rate for collecting stats.
            sucesss_queue (Queue): A queue to indicate the success of stats collection.

        Returns:
            Dict: The updated dictionary containing the collected stats as {pid: RawStats}.

        Raises:
            Exception: If there is an error collecting the stats.
        """
        # Collect current CPU and RAM stats for the process and its children
        try:
            cpu_percent, memory_percent, rss_bytes, vms_bytes = self.get_current_stats(self.pid, refresh_rate)
            if self.pid not in stats:
                stats[self.pid] = RawStats()
            stats[self.pid].cpu_percent.append(cpu_percent)
            stats[self.pid].memory_percent.append(memory_percent)
            stats[self.pid].rss_bytes.append(rss_bytes)
            stats[self.pid].vms_bytes.append(vms_bytes)
            if find_children:

                for child in psutil.Process(self.pid).children(recursive=True):
                    try:
                        if child.pid == current_process().pid:  # Avoid counting the current process
                            continue
                        cpu_percent, memory_percent, rss_bytes, vms_bytes = self.get_current_stats(
                            child.pid, refresh_rate
                        )
                        if child.pid not in stats:
                            stats[child.pid] = RawStats()
                        stats[child.pid].cpu_percent.append(cpu_percent)
                        stats[child.pid].memory_percent.append(memory_percent)
                        stats[child.pid].rss_bytes.append(rss_bytes)
                        stats[child.pid].vms_bytes.append(vms_bytes)
                    except Exception:
                        continue  # It is possible for some children processes to not exist, so we skip them

            sucesss_queue.put(True)
        except Exception as e:
            print(f"Error collecting cpu and ram stats: {e}")
            sucesss_queue.put(False)
        finally:
            return stats

    @staticmethod
    def get_current_stats(pid: int, refresh_rate: float) -> Tuple[float, float, int, int]:
        """
        Get the current CPU and memory usage statistics for a given process ID (PID).

        Parameters:
            pid (int): The process ID (PID) of the process to get the stats for.
            refresh_rate (float): The interval (in seconds) to refresh the CPU usage.

        Returns:
            Tuple[float, float, int, int]: A tuple containing the CPU percentage, memory percentage, RSS (resident set size) in bytes, and VMS (virtual memory size) in bytes.

         Note:
            - The CPU percentage is calculated using `psutil.Process.cpu_percent()` with the given `refresh_rate`.
            - The memory information is obtained using `psutil.Process.as_dict()` with the attributes "memory_info" and "memory_percent".
            - If there is an error getting the stats, the function returns 0.0 for CPU and memory percentages, and 0 for RSS and VMS.
        """
        # Use psutil to get the stats for a given PID
        try:
            p = psutil.Process(pid)
            cpu_percent = p.cpu_percent(interval=refresh_rate)
            memory_info = p.as_dict(attrs=["memory_info", "memory_percent"])
            memory_percent = memory_info["memory_percent"]
            rss_bytes = memory_info["memory_info"].rss
            vms_bytes = memory_info["memory_info"].vms
        except Exception:
            # print(f"Error getting cpu and ram stats for PID {pid}. {e}")
            return 0.0, 0.0, 0, 0
        return cpu_percent, memory_percent, rss_bytes, vms_bytes

    def collect_io_counters(self, stats, find_children: bool, sucesss_queue: Queue) -> Dict[int, RawStats]:
        """
        Collects IO stats for the process and its children.

        Args:
            stats (Dict): A dictionary to store the collected stats.
            find_children (bool): Whether to collect stats for the process's children.
            sucesss_queue (Queue): A queue to communicate success or failure.

        Returns:
            Dict: The updated stats dictionary in form of {pid: RawStats}.

        Note:
            - If the platform is "darwin" (macos), the function returns the stats dictionary as is since IO stats are not supported for macOS.
            - The IO stats for the process and its children are collected using `self.get_io_counters()`.
            - The stats are stored in the `stats` dictionary with the process ID as the key.
            - If `find_children` is True, the function iterates over the process's children and collects their IO stats.
            - If a child process does not exist, it is skipped.
            - The function puts True in the `sucesss_queue` if the stats collection is successful, False otherwise.
            - If there is an exception during the stats an error message is printed and False is put in the `sucesss_queue`.
        """
        if platform == "darwin":
            return stats
        # Collect IO stats for the process and its children
        try:
            io_read_count, io_write_count, io_read_bytes, io_write_bytes = self.get_io_counters(self.pid)
            if self.pid not in stats:
                stats[self.pid] = RawStats()
            stats[self.pid].io_read_count = io_read_count
            stats[self.pid].io_write_count = io_write_count
            stats[self.pid].io_read_bytes = io_read_bytes
            stats[self.pid].io_write_bytes = io_write_bytes

            if find_children:
                for child in psutil.Process(self.pid).children(recursive=True):
                    try:
                        if child.pid == current_process().pid:  # Avoid counting the current process
                            continue
                        io_read_count, io_write_count, io_read_bytes, io_write_bytes = self.get_io_counters(child.pid)
                        if child.pid not in stats:
                            stats[child.pid] = RawStats()
                        stats[child.pid].io_read_count = io_read_count
                        stats[child.pid].io_write_count = io_write_count
                        stats[child.pid].io_read_bytes = io_read_bytes
                        stats[child.pid].io_write_bytes = io_write_bytes
                    except Exception:
                        if child.pid in stats and (
                            stats[child.pid].io_read_count != 0
                            and stats[child.pid].io_write_count != 0  # noqa: W503
                            and stats[child.pid].io_read_bytes != 0  # noqa: W503
                            and stats[child.pid].io_write_bytes != 0  # noqa: W503
                        ):
                            continue  # This continue is to make the code more clear, but the whole condition could be removed

                        continue  # It is possible for some children processes to not exist, so we skip them

            sucesss_queue.put(True)
        except Exception as e:
            print(f"Error collecting io stats: {e}")
            sucesss_queue.put(False)
        finally:
            return stats

    @staticmethod
    def get_io_counters(pid: int) -> Tuple[int, int, int, int]:
        """
        Get the IO counters for a given process ID.

        Args:
            pid (int): The process ID of the process to get the IO counters for.

        Returns:
            Tuple[int, int, int, int]: A tuple containing the read count, write count, read bytes, and write bytes of the process's IO counters.

        Note:
            If there is an error getting the stats for the process ID, the function returns 0 for all counters.
        """
        try:
            p = psutil.Process(pid)
        except Exception:
            print(f"Error getting stats for PID {pid}")
            return 0, 0, 0, 0
        io_counters = p.io_counters()  # type: ignore
        return io_counters.read_count, io_counters.write_count, io_counters.read_bytes, io_counters.write_bytes

    def calculate_statistics_from_data(self, raw_stats: Dict[int, RawStats]) -> Dict[int, Stats]:
        """
        Calculate statistics from the given raw statistics data.
        Args:
            raw_stats (Dict[int, RawStats]): A dictionary containing the raw statistics data, where the keys are process IDs and the values are RawStats objects.
        Returns:
            Dict[int, Stats]: A dictionary containing the calculated statistics, where the keys are process IDs and the values are Stats objects. Only the statistics for non-empty RawStats objects are included.
        """
        return {pid: self.calculate_statistics(pid_data) for pid, pid_data in raw_stats.items() if pid_data}

    @staticmethod
    def calculate_statistics(data: RawStats) -> Stats:
        """
        Calculates the maximum CPU percentage, average CPU percentage, average memory percentage, average RSS bytes,
        maximum RSS bytes, average VMS bytes, maximum VMS bytes, write count, read count, write bytes,
        and read bytes from the given RawStats object.

        Args:
            data (RawStats): The data to calculate statistics from.

        Returns:
            Stats: The calculated statistics.

        """
        return Stats(
            cpu_percentage_max=max(data.cpu_percent) if data.cpu_percent else 0.0,
            cpu_percentage_avg=mean(data.cpu_percent) if data.cpu_percent else 0.0,
            memory_percentage_avg=mean(data.memory_percent) if data.memory_percent else 0.0,
            rss_bytes_avg=mean(data.rss_bytes) if data.rss_bytes else 0.0,
            rss_bytes_max=max(data.rss_bytes) if data.rss_bytes else 0,
            vms_bytes_avg=mean(data.vms_bytes) if data.vms_bytes else 0.0,
            vms_bytes_max=max(data.vms_bytes) if data.vms_bytes else 0,
            write_count=data.io_write_count if data.io_write_count is not None else 0,
            read_count=data.io_read_count if data.io_read_count is not None else 0,
            write_bytes=data.io_write_bytes if data.io_write_bytes is not None else 0,
            read_bytes=data.io_read_bytes if data.io_read_bytes is not None else 0,
        )

    @staticmethod
    def subtract_stats(main: Dict[int, Stats], other: Dict[int, Stats]) -> Dict[int, Stats]:
        """
        Subtracts the statistics from the `other` dictionary from the statistics in the `main` dictionary.

        Args:
            main (Dict[int, Stats]): A dictionary mapping process IDs to their respective statistics.
            other (Dict[int, Stats]): A dictionary mapping process IDs to their respective statistics.

        Returns:
            Dict[int, Stats]: A dictionary mapping process IDs to their respective statistics after subtraction.

        The function subtracts the statistics from the `other` dictionary from the statistics in the `main` dictionary.
        It iterates over the process IDs in the `main` dictionary and checks if the corresponding process ID exists in the `other` dictionary.
        If it does, it subtracts the statistics from the `other` dictionary from the statistics in the `main` dictionary.
        The resulting statistics are stored in the `result` dictionary.
        If the corresponding process ID does not exist in the `other` dictionary, the statistics from the `main` dictionary are copied to the `result` dictionary.
        Finally, the function returns the `result` dictionary.

        Note:
            - The CPU statistics are not subtracted.
            - The statistics are subtracted element-wise, and the resulting values are capped at 0.0 for floating-point values and 0 for integer values.
        """
        result = {}
        if not main:
            return result
        for pid, stats_main in main.items():
            if pid in other:
                stats_b = other[pid]
                subtracted_stats = Stats(
                    # cpu is not subtracted
                    cpu_percentage_max=stats_main.cpu_percentage_max,
                    cpu_percentage_avg=stats_main.cpu_percentage_avg,
                    memory_percentage_avg=max(stats_main.memory_percentage_avg - stats_b.memory_percentage_avg, 0.0),
                    rss_bytes_avg=max(stats_main.rss_bytes_avg - stats_b.rss_bytes_avg, 0.0),
                    rss_bytes_max=max(stats_main.rss_bytes_max - stats_b.rss_bytes_max, 0),
                    vms_bytes_avg=max(stats_main.vms_bytes_avg - stats_b.vms_bytes_avg, 0.0),
                    vms_bytes_max=max(stats_main.vms_bytes_max - stats_b.vms_bytes_max, 0),
                    write_count=max(stats_main.write_count - stats_b.write_count, 0),
                    read_count=max(stats_main.read_count - stats_b.read_count, 0),
                    write_bytes=max(stats_main.write_bytes - stats_b.write_bytes, 0),
                    read_bytes=max(stats_main.read_bytes - stats_b.read_bytes, 0),
                )
                result[pid] = subtracted_stats
            else:
                result[pid] = stats_main

        return result

    @staticmethod
    def get_final_stats(stats: Dict[int, Stats]):
        """
        Calculates the final statistics by summing up the statistics of all processes.
        Args:
            stats (Dict[int, Stats]): A dictionary mapping process IDs to their respective statistics.
        Returns:
            Stats: The final statistics.
        This function iterates over all the statistics in the `stats` dictionary and sums up their respective values.
        The final statistics are stored in the `final_stats` object, which is then returned.
        If the `stats` dictionary is empty, an empty `Stats` object is returned.
        """
        final_stats = Stats()
        if not stats:
            return final_stats
        for _, stat in stats.items():
            final_stats.cpu_percentage_max += stat.cpu_percentage_max
            final_stats.cpu_percentage_avg += stat.cpu_percentage_avg
            final_stats.memory_percentage_avg += stat.memory_percentage_avg
            final_stats.rss_bytes_avg += stat.rss_bytes_avg
            final_stats.rss_bytes_max += stat.rss_bytes_max
            final_stats.vms_bytes_avg += stat.vms_bytes_avg
            final_stats.vms_bytes_max += stat.vms_bytes_max
            final_stats.write_count += stat.write_count
            final_stats.read_count += stat.read_count
            final_stats.write_bytes += stat.write_bytes
            final_stats.read_bytes += stat.read_bytes
        return final_stats
