"""
Opt-in accuracy checks (not part of the default `*test*.py` discovery).

They compare metrit's measurements against known workloads (a fixed allocation, a busy
loop, a fixed number of IO bytes, a child process). Tolerances are deliberately generous
because sampling on shared CI runners is noisy. Run them with `make test-accuracy`.
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest

from metrit.core import call_func

MB = 1024 * 1024


def _measure(find_children, func, *args):
    _, monitoring = call_func(find_children, func, *args)
    return monitoring.get_data()


def allocate_and_hold(mb, seconds=0.4):
    block = bytearray(mb * MB)
    for i in range(0, len(block), 4096):
        block[i] = 1
    time.sleep(seconds)
    return len(block)


def burn_cpu(seconds=0.5):
    end = time.perf_counter() + seconds
    x = 0
    while time.perf_counter() < end:
        x += 1
    return x


def write_and_read(nbytes=MB, seconds=0.3):
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b"a" * nbytes)
            f.flush()
            os.fsync(f.fileno())
        with open(path, "rb") as f:
            f.read()
        time.sleep(seconds)
    finally:
        os.remove(path)


def spawn_child(mb, seconds=0.5):
    code = (
        f"import time; b=bytearray({mb}*1024*1024);"
        f" [b.__setitem__(i,1) for i in range(0,len(b),4096)]; time.sleep({seconds})"
    )
    subprocess.run([sys.executable, "-c", code], check=False)
    return "done"


class TestAccuracy(unittest.TestCase):
    def test_memory_growth_matches_allocation(self):
        stats = _measure(False, allocate_and_hold, 20)
        target = 20 * MB
        self.assertGreater(stats.rss_bytes_growth, target * 0.5)
        self.assertLess(stats.rss_bytes_growth, target * 1.8)

    def test_peak_is_at_least_growth(self):
        stats = _measure(False, allocate_and_hold, 20)
        self.assertGreaterEqual(stats.rss_bytes_max, stats.rss_bytes_growth)

    def test_cpu_busy_loop_uses_about_one_core(self):
        stats = _measure(False, burn_cpu, 0.5)
        self.assertGreater(stats.cpu_percentage_avg, 30.0)

    def test_io_bytes_roughly_match(self):
        nbytes = 2 * MB
        stats = _measure(False, write_and_read, nbytes)
        self.assertGreater(stats.write_bytes, nbytes * 0.5)
        self.assertGreater(stats.read_bytes, nbytes * 0.5)

    def test_children_are_measured(self):
        stats = _measure(True, spawn_child, 30)
        self.assertGreater(stats.rss_bytes_growth, 15 * MB)


if __name__ == "__main__":
    unittest.main()
