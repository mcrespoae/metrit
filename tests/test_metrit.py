import os
import unittest
from time import sleep

from metrit import metrit


@metrit
class MeasureTestClassWithArgs:
    @metrit
    def __init__(self, a: int = 1, b: int = 2):
        self.sum = a + b


@metrit
class MeasureTestClass:
    @metrit
    def metrit_basic(self, a: int = 1, b: int = 2):
        return a + b

    @metrit
    @staticmethod
    def static_method(a: int = 1, b: int = 2):
        return a + b

    @metrit
    @classmethod
    def class_method(cls, a: int = 1, b: int = 2):
        return cls.__name__, a + b


@metrit
def fill_ram(size_in_mb, duration_in_seconds):
    size_in_bytes = size_in_mb * 1024 * 1024
    _ = bytearray(size_in_bytes)
    sleep(duration_in_seconds)
    return 1 + 2


@metrit()
def cpu_intensive(a: int = 1, b: int = 2) -> int:
    for _ in range(10):
        for _ in range(10_000_000):
            pass
    return a + b


@metrit
def recursive_func(n):
    if n < 2:
        return n
    return recursive_func(n - 2) + recursive_func(n - 1)


def fib(n):
    if n < 2:
        return n
    return fib(n - 2) + fib(n - 1)


@metrit
def wrapped_recursive_func(n):
    return fib(n)


@metrit
def simulate_writes_and_reads(num_writes=5_000, data_size=1024):
    file = ".temp_file"
    with open(file, "wb") as f:
        for _ in range(num_writes):
            f.write(b"a" * data_size)
            f.flush()

    with open(file, "rb") as f:
        f.read()
    os.remove(file)


class TestmetritFunctions(unittest.TestCase):

    def test_MeasureTestClassWithArgs(self):
        obj = MeasureTestClassWithArgs(3, b=6)
        self.assertEqual(obj.sum, 9)

    def test_metrit_basic(self):
        obj = MeasureTestClass()
        result = obj.metrit_basic()
        self.assertEqual(result, 3)

    def test_static_method(self):
        result = MeasureTestClass.static_method()
        self.assertEqual(result, 3)

    def test_class_method(self):
        obj = MeasureTestClass()
        class_name, result = obj.class_method(3, b=4)
        self.assertEqual(result, 7)
        self.assertEqual(class_name, "MeasureTestClass")

    def test_fill_ram(self):
        result = fill_ram(1, 1)  # 1 MB for 1 second
        self.assertEqual(result, 3)

    def test_cpu_intensive(self):
        result = cpu_intensive(3, b=4)
        self.assertEqual(result, 7)

    def test_recursive_func(self):
        result = recursive_func(5)
        self.assertEqual(result, 5)  # fib(5) is 5

    def test_wrapped_recursive_func(self):
        result = wrapped_recursive_func(5)
        self.assertEqual(result, 5)  # fib(5) is 5

    def test_simulate_writes_and_reads(self):
        simulate_writes_and_reads(100, 1024)  # Smaller number of writes for testing purposes


if __name__ == "__main__":
    unittest.main()