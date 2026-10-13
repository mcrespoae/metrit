import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from metrit.Monitoring import Monitoring
from metrit.Stats import Stats


class FakeQueue:
    def __init__(self, items=None):
        self._items = list(items or [])

    def empty(self):
        return not self._items

    def get(self, *args, **kwargs):  # noqa: ARG002
        return self._items.pop(0)

    def put(self, item):
        self._items.append(item)

    def close(self):
        pass


class TestHasProcessCrashed(unittest.TestCase):
    def test_empty_queue_is_not_a_crash(self):
        self.assertFalse(Monitoring.has_process_crashed(FakeQueue([])))

    def test_all_successful_is_not_a_crash(self):
        self.assertFalse(Monitoring.has_process_crashed(FakeQueue([True, True])))

    def test_failure_is_a_crash(self):
        self.assertTrue(Monitoring.has_process_crashed(FakeQueue([True, False])))


class TestMonitoringPrint(unittest.TestCase):
    def test_print_verbose_contains_fields(self):
        monitoring = Monitoring()
        monitoring.formated_stats = Stats(
            cpu_percentage_max=12.34,
            cpu_percentage_avg=5.0,
            memory_percentage_max=6.0,
            memory_percentage_avg=3.0,
            rss_bytes_max=2048,
            rss_bytes_growth=1024,
            rss_bytes_avg=1536,
            vms_bytes_max=4096,
            vms_bytes_growth=2048,
            vms_bytes_avg=3072,
            read_count=5,
            write_count=2,
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            monitoring.print(True, "my_func", (1,), {"b": 2})

        output = buffer.getvalue()
        self.assertIn("metrit data for function my_func", output)
        self.assertIn("Args: (1,).", output)
        self.assertIn("Kwargs: {'b': 2}.", output)
        self.assertIn("Maximum CPU usage: 12.34%.", output)
        self.assertIn("Peak memory usage: 6.00%.", output)
        self.assertIn("Peak RSS memory usage: 2.00KB.", output)
        self.assertIn("RSS memory growth: 1.00KB.", output)

    def test_print_concise_contains_summary(self):
        monitoring = Monitoring()
        monitoring.formated_stats = Stats(rss_bytes_max=1024, cpu_percentage_avg=1.5, read_bytes=10, write_bytes=20)

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            monitoring.print(False, "my_func", (), {})

        output = buffer.getvalue()
        self.assertIn("Function 'my_func'", output)
        self.assertIn("1.00KB peak memory", output)
        self.assertIn("1.50% avg of CPU", output)

    def test_print_truncates_long_function_name(self):
        monitoring = Monitoring()
        monitoring.formated_stats = Stats()
        long_name = "a" * 40

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            monitoring.print(False, long_name, (), {})

        output = buffer.getvalue()
        self.assertIn("...", output)
        self.assertNotIn("a" * 40, output)


class TestMonitoringGracefulDegradation(unittest.TestCase):
    def test_take_snapshot_without_data_does_not_hang(self):
        with mock.patch("metrit.Monitoring.Queue", FakeQueue), mock.patch("metrit.Monitoring.Process") as process_cls:
            process_cls.return_value.is_alive.return_value = False
            monitoring = Monitoring()
            monitoring.take_snapshot()  # must not raise or block

        self.assertEqual(monitoring.baseline_io, {})
        self.assertEqual(monitoring.baseline_totals.rss_bytes, [])

    def test_stop_monitoring_without_data_does_not_hang(self):
        monitoring = Monitoring()
        monitoring.stop_queue = FakeQueue()
        monitoring.data_pool_queue = FakeQueue()  # empty: no stats will arrive
        monitoring.success_queue = FakeQueue([True])
        monitoring.pooling_process = mock.MagicMock()
        monitoring.pooling_process.is_alive.return_value = False

        monitoring.stop_monitoring()  # must not raise or block

        self.assertEqual(monitoring.pool_io, {})
        self.assertEqual(monitoring.pool_totals.rss_bytes, [])


if __name__ == "__main__":
    unittest.main()
