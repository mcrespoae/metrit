from multiprocessing import Queue, current_process
from statistics import mean
from sys import platform
from typing import Dict

import psutil

from .Stats import RawStats, Stats


class StatCollector:
    def __init__(self, pid):
        self.pid = pid
        self.stats = {}

    def collect_cpu_ram_stats(self, stats: dict, find_children: bool, refresh_rate: float, sucesss_queue: Queue):

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
    def get_current_stats(pid, refresh_rate):

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

    def collect_io_counters(self, stats, find_children: bool, sucesss_queue: Queue):
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
                        continue  # It is possible for some children processes to not exist, so we skip them

            sucesss_queue.put(True)
        except Exception as e:
            print(f"Error collecting io stats: {e}")
            sucesss_queue.put(False)
        finally:
            return stats

    @staticmethod
    def get_io_counters(pid):
        try:
            p = psutil.Process(pid)
        except Exception:
            print(f"Error getting stats for PID {pid}")
            return 0, 0, 0, 0
        io_counters = p.io_counters()  # type: ignore
        return io_counters.read_count, io_counters.write_count, io_counters.read_bytes, io_counters.write_bytes

    def calculate_statistics_from_data(self, raw_stats):
        return {pid: self.calculate_statistics(pid_data) for pid, pid_data in raw_stats.items() if pid_data}

        # Collect the final stats

    @staticmethod
    def calculate_statistics(data):
        return Stats(
            cpu_percentage_max=max(data.cpu_percent),
            cpu_percentage_avg=mean(data.cpu_percent),
            memory_percentage_avg=mean(data.memory_percent),
            rss_bytes_avg=mean(data.rss_bytes),
            rss_bytes_max=max(data.rss_bytes),
            vms_bytes_avg=mean(data.vms_bytes),
            vms_bytes_max=max(data.vms_bytes),
            write_count=data.io_write_count,
            read_count=data.io_read_count,
            write_bytes=data.io_write_bytes,
            read_bytes=data.io_read_bytes,
        )

    @staticmethod
    def subtract_stats(main: Dict[int, Stats], other: Dict[int, Stats]) -> Dict[int, Stats]:
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
