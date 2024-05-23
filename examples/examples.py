import os
import time

# Deactivate the decorator
from measurit import measureit

# from measurit import MeasuritConfig
# MeasuritConfig.ACTIVE = True  # Activates the decorator. Default option
# MeasuritConfig.ACTIVE = False  # Deactivates the decorator


@measureit
class MeasureTestClassWithArgs:
    @measureit
    def __init__(self, a: int = 1, b: int = 2):
        self.sum = a + b


@measureit
class MeasureTestClass:
    @measureit
    def measureit_basic(self, a: int = 1, b: int = 2):
        return a + b

    @measureit
    @staticmethod
    def static_method(a: int = 1, b: int = 2):
        return a + b

    @measureit
    @classmethod
    def class_method(cls, a: int = 1, b: int = 2):
        return cls.__name__, a + b


@measureit
def fill_ram(size_in_mb, duration_in_seconds):
    """
    Simulate filling RAM by allocating memory.

    :param size_in_mb: Amount of memory to allocate in MB.
    :param duration_in_seconds: Duration to hold the memory allocated in seconds.
    """
    # Convert MB to bytes
    size_in_bytes = size_in_mb * 1024 * 1024
    # Allocate memory
    _ = bytearray(size_in_bytes)  # Allocate memory

    # Hold the memory for the specified duration
    time.sleep(duration_in_seconds)
    return 1 + 2


@measureit()
def cpu_intensive(a: int = 1, b: int = 2) -> int:
    # Simulate some work
    for _ in range(10):
        for _ in range(10_000_000):
            pass  #
    return a + b


@measureit
def recursive_func(n):
    if n < 2:
        return n
    return recursive_func(n - 2) + recursive_func(n - 1)


def fib(n):
    if n < 2:
        return n
    return fib(n - 2) + fib(n - 1)


@measureit
def wrapped_recursive_func(n):
    return fib(n)


@measureit
def simulate_writes_and_reads(num_writes=5_000, data_size=1024):
    file = ".temp_file"
    with open(file, "wb") as f:
        for _ in range(num_writes):
            f.write(b"a" * data_size)
            f.flush()  # Ensure data is written to disk

    with open(file, "rb") as f:
        f.read()
    os.remove(file)


@measureit(verbose=True)
def main():

    print("---CLASS EXAMPLES---")
    test_class_args = MeasureTestClassWithArgs(3, b=6)
    if test_class_args.sum != 9:
        print("test_class_args.sum != 9")
        exit()

    test_class = MeasureTestClass()
    result = test_class.measureit_basic()
    if result != 3:
        print("test_class.measureit_basic() != 3")
        exit()

    result = test_class.static_method()
    if result != 3:
        print("test_class.static_method() != 3")
        exit()

    class_name, result = test_class.class_method(3, b=4)
    if result != 7 or class_name != "MeasureTestClass":
        print("test_class.class_method() != ('MeasureTestClass', 7)")
        exit()
    print("---END CLASS EXAMPLES---\n")

    print("---RECURSIVE EXAMPLES---")
    wrapped_recursive_func(21)
    recursive_func(21)
    print("---END RECURSIVE EXAMPLES---\n")

    print("---OTHER EXAMPLES---")
    fill_ram(100, 5)
    cpu_intensive(3, b=4)
    simulate_writes_and_reads()
    print("---END OTHER EXAMPLES---\n")


if __name__ == "__main__":
    main()
