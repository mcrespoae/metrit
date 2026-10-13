import io
import os
import shutil
import tempfile
import time
import unittest
from contextlib import redirect_stdout

from multiprocess import current_process  # type: ignore

from metrit.core import MetritConfig, metrit

MetritConfig.ACTIVE = True


@metrit(isolate=True)
def raising_once(counter_path):
    # Appends to a shared file so we can detect a double execution across processes.
    # Before the fix, a user exception made metrit retry the function in the main process.
    with open(counter_path, "a", encoding="utf-8") as f:
        f.write("call\n")
    raise ValueError("boom from the isolated function")


@metrit(isolate=True)
def hard_crash_then_recover():
    # Simulate a hard crash (no Python exception, no report) inside the isolated
    # process. metrit must detect the missing report and recover in the main process
    # instead of hanging forever.
    if current_process().name != "MainProcess":
        # Give the nested monitor process time to finish spawning before the hard
        # exit, so the crash is the only thing under test.
        time.sleep(1.5)
        os._exit(0)
    return "recovered"


@metrit(isolate=True)
def sometimes_raises(should_raise=False):
    if should_raise:
        raise RuntimeError("boom")
    return 42


class TestIsolationErrors(unittest.TestCase):
    def setUp(self):
        MetritConfig.ACTIVE = True
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_user_exception_is_not_executed_twice(self):
        counter_path = os.path.join(self.tmpdir, "counter.txt")

        with self.assertRaises(ValueError) as ctx:
            raising_once(counter_path)

        self.assertEqual(str(ctx.exception), "boom from the isolated function")
        with open(counter_path, encoding="utf-8") as f:
            calls = f.read().count("call")
        self.assertEqual(calls, 1, "the function must run exactly once when it raises")

    def test_user_exception_is_not_wrapped_in_isolation_error(self):
        with self.assertRaises(ValueError):
            raising_once(os.path.join(self.tmpdir, "counter2.txt"))

    def test_hard_crash_falls_back_to_main_process(self):
        # Would hang forever without the queue timeout / exitcode detection.
        self.assertEqual(hard_crash_then_recover(), "recovered")

    def test_exception_does_not_leak_recursion_stack(self):
        with self.assertRaises(RuntimeError):
            sometimes_raises(should_raise=True)

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = sometimes_raises()

        self.assertEqual(result, 42)
        # Before the fix, the stack leaked and the next call was misdetected as
        # recursive, so no metrics were printed at all.
        self.assertIn("Function 'sometimes_raises'", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
