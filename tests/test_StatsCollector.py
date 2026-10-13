import types
import unittest
from sys import platform
from unittest import mock

from multiprocess import current_process  # type: ignore

from metrit.StatCollector import RawStats, StatCollector, Stats


class _FakeChild:
    def __init__(self, pid):
        self.pid = pid


class _FakePsutilProcess:
    def __init__(self, pid):
        self.pid = pid

    def cpu_percent(self, interval=None):  # noqa: ARG002
        return 10.0

    def memory_percent(self):
        return 1.5

    def memory_info(self):
        return types.SimpleNamespace(rss=1000, vms=2000)


class _FakeParentProcess:
    def __init__(self, children):
        self._children = children

    def children(self, recursive=False):  # noqa: ARG002
        return self._children


class TestGetCurrentStats(unittest.TestCase):
    def setUp(self):
        self.stat_collector = StatCollector(1234)

    def test_returns_none_on_error(self):
        with mock.patch("metrit.StatCollector.psutil.Process", side_effect=Exception("gone")):
            self.assertIsNone(self.stat_collector.get_current_stats(1234))

    def test_first_sample_has_no_cpu_then_valid_cpu(self):
        with mock.patch("metrit.StatCollector.psutil.Process", side_effect=lambda pid: _FakePsutilProcess(pid)):
            first = self.stat_collector.get_current_stats(1234)
            second = self.stat_collector.get_current_stats(1234)

        assert first is not None and second is not None
        self.assertIsNone(first[0])  # CPU not valid on the priming sample
        self.assertEqual(first[1:], (1.5, 1000, 2000))
        self.assertEqual(second, (10.0, 1.5, 1000, 2000))


class TestCollectCpuRam(unittest.TestCase):
    def setUp(self):
        self.stat_collector = StatCollector(1234)

    def test_failed_samples_are_skipped(self):
        success_queue = mock.MagicMock()
        stats, totals = {}, RawStats()
        with mock.patch.object(StatCollector, "get_current_stats", return_value=None):
            stats, totals = self.stat_collector.collect_cpu_ram_stats(stats, totals, False, success_queue)

        self.assertEqual(stats, {})
        self.assertEqual(totals.rss_bytes, [])
        success_queue.put.assert_called_with(True)

    def test_samples_are_recorded_and_totaled(self):
        success_queue = mock.MagicMock()
        stats, totals = {}, RawStats()
        with mock.patch.object(StatCollector, "get_current_stats", return_value=(10.0, 1.5, 100, 200)):
            stats, totals = self.stat_collector.collect_cpu_ram_stats(stats, totals, False, success_queue)

        self.assertIn(1234, stats)
        self.assertEqual(stats[1234].cpu_percent, [10.0])
        self.assertEqual(totals.cpu_percent, [10.0])
        self.assertEqual(totals.rss_bytes, [100])

    def test_monitoring_process_is_not_counted(self):
        current_pid = current_process().pid  # type: ignore
        children = [_FakeChild(current_pid), _FakeChild(9999)]
        success_queue = mock.MagicMock()
        stats, totals = {}, RawStats()

        def fake_process(pid):
            return _FakeParentProcess(children) if pid == 1234 else _FakePsutilProcess(pid)

        with mock.patch("metrit.StatCollector.psutil.Process", side_effect=fake_process), mock.patch.object(
            StatCollector, "get_current_stats", return_value=(1.0, 2.0, 3, 4)
        ):
            stats, totals = self.stat_collector.collect_cpu_ram_stats(stats, totals, True, success_queue)

        self.assertIn(1234, stats)
        self.assertIn(9999, stats)
        self.assertNotIn(current_pid, stats)
        self.assertEqual(totals.rss_bytes, [3 + 3])  # only target (1234) + 9999 counted


class TestIO(unittest.TestCase):
    def setUp(self):
        self.stat_collector = StatCollector(1234)

    def test_get_io_counters_returns_none_on_error(self):
        with mock.patch("metrit.StatCollector.psutil.Process", side_effect=Exception("gone")):
            self.assertIsNone(self.stat_collector.get_io_counters(1234))

    def test_collect_io_does_not_overwrite_with_none(self):
        if platform == "darwin":
            self.skipTest("IO counters are not supported on macOS")

        success_queue = mock.MagicMock()
        existing = RawStats(io_read_count=7, io_write_count=8, io_read_bytes=9, io_write_bytes=10)
        stats = {1234: existing}

        with mock.patch.object(StatCollector, "get_io_counters", return_value=None):
            result = self.stat_collector.collect_io_counters(stats, False, success_queue)

        self.assertIs(result[1234], existing)
        self.assertEqual(result[1234].io_read_count, 7)
        self.assertEqual(result[1234].io_write_bytes, 10)


class TestStatsFromTotals(unittest.TestCase):
    def test_peaks_means_and_memory_max(self):
        totals = RawStats(
            cpu_percent=[10.0, 20.0, 30.0],
            memory_percent=[1.0, 2.0, 3.0],
            rss_bytes=[100, 200, 300],
            vms_bytes=[10, 20, 30],
        )
        stats = StatCollector.stats_from_totals(totals)

        self.assertEqual(stats.cpu_percentage_max, 30.0)
        self.assertEqual(stats.cpu_percentage_avg, 20.0)
        self.assertEqual(stats.memory_percentage_max, 3.0)
        self.assertEqual(stats.memory_percentage_avg, 2.0)
        self.assertEqual(stats.rss_bytes_max, 300)
        self.assertEqual(stats.rss_bytes_avg, 200.0)
        self.assertEqual(stats.vms_bytes_max, 30)

    def test_empty_totals_are_zero(self):
        self.assertEqual(StatCollector.stats_from_totals(RawStats()), Stats())


class TestFinalize(unittest.TestCase):
    def test_growth_and_io_delta(self):
        pool_totals = RawStats(
            cpu_percent=[25.0], memory_percent=[5.0], rss_bytes=[500], vms_bytes=[50]
        )
        baseline_totals = RawStats(memory_percent=[1.0], rss_bytes=[100], vms_bytes=[20])
        pool_io = {1: RawStats(io_read_count=10, io_write_count=5, io_read_bytes=100, io_write_bytes=50)}
        baseline_io = {1: RawStats(io_read_count=2, io_write_count=1, io_read_bytes=20, io_write_bytes=10)}

        stats = StatCollector.finalize(pool_totals, baseline_totals, pool_io, baseline_io)

        self.assertEqual(stats.rss_bytes_max, 500)  # absolute peak
        self.assertEqual(stats.rss_bytes_growth, 400)  # 500 - 100
        self.assertEqual(stats.vms_bytes_growth, 30)  # 50 - 20
        self.assertEqual(stats.read_count, 8)
        self.assertEqual(stats.write_count, 4)
        self.assertEqual(stats.read_bytes, 80)
        self.assertEqual(stats.write_bytes, 40)

    def test_pid_missing_from_baseline_is_counted_in_full(self):
        pool_totals = RawStats(rss_bytes=[500])
        pool_io = {99: RawStats(io_read_bytes=1234)}
        stats = StatCollector.finalize(pool_totals, RawStats(), pool_io, {})

        self.assertEqual(stats.read_bytes, 1234)
        self.assertEqual(stats.rss_bytes_growth, 500)


if __name__ == "__main__":
    unittest.main()
