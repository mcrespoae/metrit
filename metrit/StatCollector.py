import logging
from statistics import mean
from sys import platform
from typing import Dict, List, Tuple

import psutil
from multiprocess import Queue, current_process  # type: ignore

from .Stats import RawStats, Stats

logger = logging.getLogger("metrit")

_STATS_TUPLE = Tuple[float | None, float, int, int]


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
        # Persistent psutil.Process objects so cpu_percent() can be used in
        # non-blocking mode (it then reports the CPU used since the previous sample).
        self._process_cache: Dict[int, "psutil.Process"] = {}

    def _get_process(self, pid: int) -> "psutil.Process | None":
        try:
            process = self._process_cache.get(pid)
            if process is None:
                process = psutil.Process(pid)
                self._process_cache[pid] = process
            return process
        except Exception:
            self._process_cache.pop(pid, None)
            return None

    def _children_pids(self) -> List[int]:
        """PIDs of the target's descendants, excluding the monitoring process itself."""
        try:
            children = psutil.Process(self.pid).children(recursive=True)
        except Exception:
            return []
        monitoring_pid = current_process().pid  # type: ignore
        return [child.pid for child in children if child.pid != monitoring_pid]

    def prime(self, find_children: bool) -> None:
        """
        Establishes the CPU baseline for the target (and children) so that the next
        sample is a valid percentage instead of the 0.0 returned by the first call.
        """
        for pid in [self.pid] + (self._children_pids() if find_children else []):
            self.get_current_stats(pid)  # discarded; only primes the counters

    def get_current_stats(self, pid: int) -> _STATS_TUPLE | None:
        """
        Get the CPU and memory usage for a given PID.

        CPU is read with ``cpu_percent(interval=None)`` on a cached Process object, which
        returns the usage since the previous call (non-blocking). For a freshly created
        Process the CPU value is not meaningful yet, so a priming call is made and ``None``
        is returned for CPU on that first sample; callers should record memory but skip CPU.

        Returns:
            Tuple[float | None, float, int, int] | None: (cpu_percent, memory_percent, rss, vms)
            or None if the stats cannot be retrieved (e.g. the process is gone).
        """
        try:
            process = self._process_cache.get(pid)
            first_sample = process is None
            if process is None:
                process = psutil.Process(pid)
                self._process_cache[pid] = process
                process.cpu_percent(interval=None)  # prime

            cpu_percent = process.cpu_percent(interval=None)
            memory_percent = process.memory_percent()
            memory_info = process.memory_info()

            if first_sample:
                return None, memory_percent, memory_info.rss, memory_info.vms
            return cpu_percent, memory_percent, memory_info.rss, memory_info.vms
        except Exception:
            self._process_cache.pop(pid, None)
            return None

    def collect_cpu_ram_stats(
        self,
        stats: Dict[int, RawStats],
        totals: RawStats,
        find_children: bool,
        sucesss_queue: Queue,
    ) -> Tuple[Dict[int, RawStats], RawStats]:
        """
        Samples the target (and optionally its children) once, appending a per-PID sample
        to ``stats`` and a simultaneous per-tick total (sum across PIDs) to ``totals``.

        Sampling every PID in one pass means the per-PID values and the totals come from
        the same time windows, so the totals are a coherent "whole run" aggregate.

        Args:
            stats (Dict[int, RawStats]): Per-PID accumulated samples.
            totals (RawStats): Simultaneous per-tick totals (cpu/memory/rss/vms).
            find_children (bool): Whether to include child processes.
            sucesss_queue (Queue): Success/failure signal queue.

        Returns:
            Tuple[Dict[int, RawStats], RawStats]: The updated ``stats`` and ``totals``.
        """
        try:
            tick_cpu: List[float] = []
            tick_memory: List[float] = []
            tick_rss: List[int] = []
            tick_vms: List[int] = []

            def sample(pid: int) -> None:
                current = self.get_current_stats(pid)
                if current is None:
                    return
                cpu_percent, memory_percent, rss_bytes, vms_bytes = current
                pid_stats = stats.get(pid)
                if pid_stats is None:
                    pid_stats = RawStats()
                    stats[pid] = pid_stats
                if cpu_percent is not None:
                    pid_stats.cpu_percent.append(cpu_percent)
                    tick_cpu.append(cpu_percent)
                pid_stats.memory_percent.append(memory_percent)
                pid_stats.rss_bytes.append(rss_bytes)
                pid_stats.vms_bytes.append(vms_bytes)
                tick_memory.append(memory_percent)
                tick_rss.append(rss_bytes)
                tick_vms.append(vms_bytes)

            sample(self.pid)
            if find_children:
                for child_pid in self._children_pids():
                    sample(child_pid)

            if tick_rss:
                totals.memory_percent.append(sum(tick_memory))
                totals.rss_bytes.append(sum(tick_rss))
                totals.vms_bytes.append(sum(tick_vms))
            if tick_cpu:
                totals.cpu_percent.append(sum(tick_cpu))

            sucesss_queue.put(True)
        except Exception as e:
            logger.warning("Error collecting cpu and ram stats: %s", e)
            sucesss_queue.put(False)
        return stats, totals

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
            - On macOS (darwin) IO counters are not available and the stats are returned as is.
            - IO counters are cumulative per process; the latest value is stored so the
              baseline can be subtracted later, giving IO performed during the run.
            - The monitoring process itself is excluded.
        """
        if platform == "darwin":
            return stats
        # Collect IO stats for the process and its children
        try:
            counters = self.get_io_counters(self.pid)
            if counters is not None:
                if self.pid not in stats:
                    stats[self.pid] = RawStats()
                (
                    stats[self.pid].io_read_count,
                    stats[self.pid].io_write_count,
                    stats[self.pid].io_read_bytes,
                    stats[self.pid].io_write_bytes,
                ) = counters

            if find_children:
                for child_pid in self._children_pids():
                    child_counters = self.get_io_counters(child_pid)
                    if child_counters is None:
                        continue  # Child vanished before its counters could be read, skip it
                    if child_pid not in stats:
                        stats[child_pid] = RawStats()
                    (
                        stats[child_pid].io_read_count,
                        stats[child_pid].io_write_count,
                        stats[child_pid].io_read_bytes,
                        stats[child_pid].io_write_bytes,
                    ) = child_counters

            sucesss_queue.put(True)
        except Exception as e:
            logger.warning("Error collecting io stats: %s", e)
            sucesss_queue.put(False)
        finally:
            return stats

    @staticmethod
    def get_io_counters(pid: int) -> Tuple[int, int, int, int] | None:
        """
        Get the IO counters for a given process ID.

        Args:
            pid (int): The process ID of the process to get the IO counters for.

        Returns:
            Tuple[int, int, int, int] | None: read count, write count, read bytes and write
            bytes, or None if they cannot be read (e.g. the process is gone).
        """
        try:
            p = psutil.Process(pid)
            io_counters = p.io_counters()  # type: ignore
        except Exception:
            return None
        return io_counters.read_count, io_counters.write_count, io_counters.read_bytes, io_counters.write_bytes

    @staticmethod
    def stats_from_totals(totals: RawStats) -> Stats:
        """
        Builds the aggregated :class:`Stats` from the simultaneous per-tick totals.

        RSS/VMS peaks are absolute; memory percentages are absolute; CPU is the sum across
        the measured processes (see ``find_children``).
        """
        return Stats(
            cpu_percentage_max=max(totals.cpu_percent) if totals.cpu_percent else 0.0,
            cpu_percentage_avg=mean(totals.cpu_percent) if totals.cpu_percent else 0.0,
            memory_percentage_avg=mean(totals.memory_percent) if totals.memory_percent else 0.0,
            memory_percentage_max=max(totals.memory_percent) if totals.memory_percent else 0.0,
            rss_bytes_avg=mean(totals.rss_bytes) if totals.rss_bytes else 0.0,
            rss_bytes_max=max(totals.rss_bytes) if totals.rss_bytes else 0,
            vms_bytes_avg=mean(totals.vms_bytes) if totals.vms_bytes else 0.0,
            vms_bytes_max=max(totals.vms_bytes) if totals.vms_bytes else 0,
        )

    @staticmethod
    def finalize(
        pool_totals: RawStats,
        baseline_totals: RawStats,
        pool_io: Dict[int, RawStats],
        baseline_io: Dict[int, RawStats],
    ) -> Stats:
        """
        Combines pooled totals, the baseline snapshot and IO counters into the final Stats.

        - RSS/VMS peaks are absolute; growth is peak minus the baseline peak.
        - IO is the sum over PIDs of (cumulative at end - cumulative at baseline), so it is
          the IO actually performed during the run.
        """
        result = StatCollector.stats_from_totals(pool_totals)
        baseline = StatCollector.stats_from_totals(baseline_totals)
        result.rss_bytes_growth = max(result.rss_bytes_max - baseline.rss_bytes_max, 0)
        result.vms_bytes_growth = max(result.vms_bytes_max - baseline.vms_bytes_max, 0)

        for pid, counters in pool_io.items():
            base = baseline_io.get(pid)
            if base is None:
                result.read_count += counters.io_read_count
                result.write_count += counters.io_write_count
                result.read_bytes += counters.io_read_bytes
                result.write_bytes += counters.io_write_bytes
            else:
                result.read_count += max(counters.io_read_count - base.io_read_count, 0)
                result.write_count += max(counters.io_write_count - base.io_write_count, 0)
                result.read_bytes += max(counters.io_read_bytes - base.io_read_bytes, 0)
                result.write_bytes += max(counters.io_write_bytes - base.io_write_bytes, 0)

        return result
