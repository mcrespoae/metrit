import unittest

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


if __name__ == "__main__":
    unittest.main()
