import unittest
from sys import platform
from unittest import mock

from multiprocess import current_process  # type: ignore

from metrit.StatCollector import RawStats, StatCollector, Stats


class TestCalculateStatisticsFromData(unittest.TestCase):

    def setUp(self):
        self.stat_collector = StatCollector(1)

    def test_empty_raw_stats(self):
        raw_stats = {}
        result = self.stat_collector.calculate_statistics_from_data(raw_stats)
        self.assertEqual(result, {})

    def test_non_empty_raw_stats(self):
        raw_stats = {
            1: RawStats(
                cpu_percent=[10, 20, 30],
                memory_percent=[50, 60, 70],
                rss_bytes=[100, 200, 300],
                vms_bytes=[500, 600, 700],
                io_write_count=1,
                io_read_count=2,
                io_write_bytes=3,
                io_read_bytes=4,
            ),
            2: RawStats(
                cpu_percent=[40, 50, 60],
                memory_percent=[80, 90, 100],
                rss_bytes=[400, 500, 600],
                vms_bytes=[800, 900, 1000],
                io_write_count=5,
                io_read_count=6,
                io_write_bytes=7,
                io_read_bytes=8,
            ),
        }
        expected_result = {
            1: Stats(
                cpu_percentage_max=30,
                cpu_percentage_avg=20,
                memory_percentage_avg=60,
                rss_bytes_avg=200,
                rss_bytes_max=300,
                vms_bytes_avg=600,
                vms_bytes_max=700,
                write_count=1,
                read_count=2,
                write_bytes=3,
                read_bytes=4,
            ),
            2: Stats(
                cpu_percentage_max=60,
                cpu_percentage_avg=50,
                memory_percentage_avg=90,
                rss_bytes_avg=500,
                rss_bytes_max=600,
                vms_bytes_avg=900,
                vms_bytes_max=1000,
                write_count=5,
                read_count=6,
                write_bytes=7,
                read_bytes=8,
            ),
        }
        result = self.stat_collector.calculate_statistics_from_data(raw_stats)
        self.assertEqual(result, expected_result)

    def test_raw_stats_with_empty_pid_data(self):
        raw_stats = {
            1: RawStats(),
            2: RawStats(
                cpu_percent=[40, 50, 60],
                memory_percent=[80, 90, 100],
                rss_bytes=[400, 500, 600],
                vms_bytes=[800, 900, 1000],
                io_write_count=5,
                io_read_count=6,
                io_write_bytes=7,
                io_read_bytes=8,
            ),
        }
        expected_result = {
            1: Stats(
                cpu_percentage_max=0.0,
                cpu_percentage_avg=0.0,
                memory_percentage_avg=0.0,
                rss_bytes_avg=0.0,
                rss_bytes_max=0,
                vms_bytes_avg=0.0,
                vms_bytes_max=0,
                write_count=0,
                read_count=0,
                write_bytes=0,
                read_bytes=0,
            ),
            2: Stats(
                cpu_percentage_max=60,
                cpu_percentage_avg=50,
                memory_percentage_avg=90,
                rss_bytes_avg=500,
                rss_bytes_max=600,
                vms_bytes_avg=900,
                vms_bytes_max=1000,
                write_count=5,
                read_count=6,
                write_bytes=7,
                read_bytes=8,
            ),
        }
        result = self.stat_collector.calculate_statistics_from_data(raw_stats)
        self.assertEqual(result, expected_result)


class TestCalculateStatistics(unittest.TestCase):
    def setUp(self):
        self.stat_collector = StatCollector(1)

    def test_calculate_statistics_with_empty_data(self):
        data = RawStats(
            cpu_percent=[],
            memory_percent=[],
            rss_bytes=[],
            vms_bytes=[],
            io_write_count=0,
            io_read_count=0,
            io_write_bytes=0,
            io_read_bytes=0,
        )
        expected_stats = Stats(
            cpu_percentage_max=0.0,
            cpu_percentage_avg=0.0,
            memory_percentage_avg=0.0,
            rss_bytes_avg=0.0,
            rss_bytes_max=0,
            vms_bytes_avg=0.0,
            vms_bytes_max=0,
            write_count=0,
            read_count=0,
            write_bytes=0,
            read_bytes=0,
        )
        self.assertEqual(self.stat_collector.calculate_statistics(data), expected_stats)

    def test_calculate_statistics_with_non_empty_data(self):
        data = RawStats(
            cpu_percent=[50, 75, 25],
            memory_percent=[50, 75, 25],
            rss_bytes=[100, 150, 200],
            vms_bytes=[100, 150, 200],
            io_write_count=10,
            io_read_count=20,
            io_write_bytes=100,
            io_read_bytes=200,
        )
        expected_stats = Stats(
            cpu_percentage_max=75.0,
            cpu_percentage_avg=50.0,
            memory_percentage_avg=50.0,
            rss_bytes_avg=150.0,
            rss_bytes_max=200,
            vms_bytes_avg=150.0,
            vms_bytes_max=200,
            write_count=10,
            read_count=20,
            write_bytes=100,
            read_bytes=200,
        )
        self.assertEqual(self.stat_collector.calculate_statistics(data), expected_stats)

    def test_calculate_statistics_with_single_value_data(self):
        data = RawStats(
            cpu_percent=[50],
            memory_percent=[50],
            rss_bytes=[100],
            vms_bytes=[100],
            io_write_count=10,
            io_read_count=20,
            io_write_bytes=100,
            io_read_bytes=200,
        )
        expected_stats = Stats(
            cpu_percentage_max=50.0,
            cpu_percentage_avg=50.0,
            memory_percentage_avg=50.0,
            rss_bytes_avg=100.0,
            rss_bytes_max=100,
            vms_bytes_avg=100.0,
            vms_bytes_max=100,
            write_count=10,
            read_count=20,
            write_bytes=100,
            read_bytes=200,
        )
        self.assertEqual(self.stat_collector.calculate_statistics(data), expected_stats)


class TestStatCollector(unittest.TestCase):
    def setUp(self):
        self.stat_collector = StatCollector(1)

    def test_subtract_stats_with_empty_dicts(self):
        main = {}
        other = {}
        result = StatCollector.subtract_stats(main, other)
        self.assertEqual(result, {})

    def test_get_final_stats_single(self):
        stats = {
            1: Stats(
                cpu_percentage_max=10,
                cpu_percentage_avg=5,
                memory_percentage_avg=3,
                rss_bytes_avg=1000,
                rss_bytes_max=2000,
                vms_bytes_avg=3000,
                vms_bytes_max=4000,
                write_count=10,
                read_count=20,
                write_bytes=100,
                read_bytes=200,
            )
        }
        expected = Stats(
            cpu_percentage_max=10,
            cpu_percentage_avg=5,
            memory_percentage_avg=3,
            rss_bytes_avg=1000,
            rss_bytes_max=2000,
            vms_bytes_avg=3000,
            vms_bytes_max=4000,
            write_count=10,
            read_count=20,
            write_bytes=100,
            read_bytes=200,
        )
        result = self.stat_collector.get_final_stats(stats)
        self.assertEqual(result, expected)

    def test_get_final_stats_multiple(self):
        stats = {
            1: Stats(
                cpu_percentage_max=10,
                cpu_percentage_avg=5,
                memory_percentage_avg=3,
                rss_bytes_avg=1000,
                rss_bytes_max=2000,
                vms_bytes_avg=3000,
                vms_bytes_max=4000,
                write_count=10,
                read_count=20,
                write_bytes=100,
                read_bytes=200,
            ),
            2: Stats(
                cpu_percentage_max=20,
                cpu_percentage_avg=10,
                memory_percentage_avg=6,
                rss_bytes_avg=2000,
                rss_bytes_max=4000,
                vms_bytes_avg=6000,
                vms_bytes_max=8000,
                write_count=20,
                read_count=40,
                write_bytes=200,
                read_bytes=400,
            ),
        }
        expected = Stats(
            cpu_percentage_max=30,
            cpu_percentage_avg=15,
            memory_percentage_avg=9,
            rss_bytes_avg=3000,
            rss_bytes_max=6000,
            vms_bytes_avg=9000,
            vms_bytes_max=12000,
            write_count=30,
            read_count=60,
            write_bytes=300,
            read_bytes=600,
        )
        result = self.stat_collector.get_final_stats(stats)
        self.assertEqual(result, expected)


class _FakeChild:
    def __init__(self, pid):
        self.pid = pid


class _FakeProcess:
    def __init__(self, children=None):
        self._children = children or []

    def children(self, recursive=False):  # noqa: ARG002
        return self._children


class TestFailedSamplesAreSkipped(unittest.TestCase):
    def setUp(self):
        self.stat_collector = StatCollector(1234)

    def test_get_current_stats_returns_none_on_error(self):
        with mock.patch("metrit.StatCollector.psutil.Process", side_effect=Exception("gone")):
            self.assertIsNone(self.stat_collector.get_current_stats(1234, 0.0))

    def test_get_io_counters_returns_none_on_error(self):
        with mock.patch("metrit.StatCollector.psutil.Process", side_effect=Exception("gone")):
            self.assertIsNone(self.stat_collector.get_io_counters(1234))

    def test_collect_cpu_ram_skips_failed_samples(self):
        success_queue = mock.MagicMock()
        stats = {}
        with mock.patch.object(StatCollector, "get_current_stats", return_value=None):
            result = self.stat_collector.collect_cpu_ram_stats(stats, False, 0.0, success_queue)

        self.assertEqual(result, {})
        success_queue.put.assert_called_with(True)

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


class TestMonitorProcessExcluded(unittest.TestCase):
    def setUp(self):
        self.stat_collector = StatCollector(1234)

    def test_monitoring_process_is_not_counted(self):
        current_pid = current_process().pid  # type: ignore
        children = [_FakeChild(current_pid), _FakeChild(9999)]
        success_queue = mock.MagicMock()
        stats = {}

        def fake_process(pid):
            return _FakeProcess(children) if pid == 1234 else _FakeProcess([])

        def fake_stats(pid, refresh_rate):  # noqa: ARG001
            return (1.0, 2.0, 3, 4)

        with mock.patch("metrit.StatCollector.psutil.Process", side_effect=fake_process), mock.patch.object(
            StatCollector, "get_current_stats", side_effect=fake_stats
        ):
            result = self.stat_collector.collect_cpu_ram_stats(stats, True, 0.0, success_queue)

        self.assertIn(1234, result)
        self.assertIn(9999, result)
        self.assertNotIn(current_pid, result)
        self.assertEqual(result[9999].rss_bytes, [3])


if __name__ == "__main__":
    unittest.main()
