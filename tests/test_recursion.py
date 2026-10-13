import io
import threading
import unittest
from contextlib import redirect_stdout

from metrit.core import MetritConfig, metrit
from metrit.utils import RecursionState, function_key

MetritConfig.ACTIVE = True


def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


@metrit(isolate=False)
def recursive_local(n):
    return n if n < 2 else recursive_local(n - 1) + recursive_local(n - 2)


@metrit(isolate=True)
def recursive_isolated(n):
    return n if n < 2 else recursive_isolated(n - 1) + recursive_isolated(n - 2)


@metrit(isolate=False)
def outer_func(n):
    return inner_func(n) + 1


@metrit(isolate=False)
def inner_func(n):
    return n * 2


class TestFunctionKey(unittest.TestCase):
    def test_key_is_stable(self):
        self.assertEqual(function_key(recursive_local), function_key(recursive_local))

    def test_mp_main_is_normalized_to_main(self):
        # spawn imports the entry script as __mp_main__; the key must not change.
        def sample():
            return 1

        sample.__module__ = "__mp_main__"
        self.assertEqual(function_key(sample)[0], "__main__")

    def test_unwraps_class_and_static_methods(self):
        class Sample:
            @staticmethod
            def static_method():
                return 1

            @classmethod
            def class_method(cls):
                return 1

        self.assertEqual(function_key(Sample.__dict__["static_method"]), function_key(Sample.static_method))
        self.assertEqual(function_key(Sample.__dict__["class_method"]), function_key(Sample.class_method))


class TestRecursionState(unittest.TestCase):
    def test_recursive_detection_counts(self):
        state = RecursionState()
        key = ("m", "f", b"")
        self.assertFalse(state.is_recursive(key))
        state.enter(key)
        self.assertTrue(state.is_recursive(key))
        state.enter(key)
        self.assertTrue(state.is_recursive(key))
        state.exit(key)
        self.assertTrue(state.is_recursive(key))
        state.exit(key)
        self.assertFalse(state.is_recursive(key))

    def test_state_is_thread_local(self):
        state = RecursionState()
        key = ("m", "f", b"")
        state.enter(key)

        seen = {}
        thread = threading.Thread(target=lambda: seen.setdefault("recursive", state.is_recursive(key)))
        thread.start()
        thread.join()

        self.assertFalse(seen["recursive"])


class TestRecursion(unittest.TestCase):
    def setUp(self):
        MetritConfig.ACTIVE = True

    def test_non_isolated_recursion_result(self):
        self.assertEqual(recursive_local(10), fib(10))

    def test_non_isolated_recursion_prints_once(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            recursive_local(8)
        self.assertEqual(buffer.getvalue().count("Function 'recursive_local'"), 1)

    def test_isolated_recursion_result(self):
        self.assertEqual(recursive_isolated(10), fib(10))

    def test_isolated_recursion_prints_once(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            recursive_isolated(8)
        self.assertEqual(buffer.getvalue().count("Function 'recursive_isolated'"), 1)

    def test_nested_functions_do_not_interfere(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = outer_func(5)

        self.assertEqual(result, 11)
        output = buffer.getvalue()
        self.assertIn("Function 'inner_func'", output)
        self.assertIn("Function 'outer_func'", output)

    def test_same_function_concurrently_in_threads(self):
        results = {}
        errors = []

        def run(name, n):
            try:
                results[name] = recursive_local(n)
            except Exception as error:  # pragma: no cover - only on regression
                errors.append(error)

        threads = [threading.Thread(target=run, args=(f"t{i}", i)) for i in range(1, 6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertFalse(errors)
        for i in range(1, 6):
            self.assertEqual(results[f"t{i}"], fib(i))


if __name__ == "__main__":
    unittest.main()
