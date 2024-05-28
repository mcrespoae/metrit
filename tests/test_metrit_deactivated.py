import os
import unittest
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from metrit.core import MetritConfig, metrit

IN_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"
MetritConfig.ACTIVE = False


class MetritTestClassDeactivated:

    @metrit()
    def metrit_basic(self, a: int = 0, b: int = 1):
        return a + b

    @metrit
    def metrit_basic_no_parenthesis(self, a: int = 0, b: int = 1):
        return a + b

    def sum(self, a: int = 1, b: int = 2):
        return a + b

    @metrit(verbose=True, find_children=True)
    def test_metrit_args(self, a: int = 0, b: int = 1):
        return self.sum(a, b)

    @metrit(isolate=True)
    @staticmethod
    def static_method(a: int = 0, b: int = 1):
        return a + b

    @metrit
    @classmethod
    def class_method(cls, a: int = 0, b: int = 1):
        return cls.__name__, a + b


class TestmetritDecoratorClassDeactivated(unittest.TestCase):
    def setUp(self):
        self.test_class = MetritTestClassDeactivated()

    def test_metrit_basic(self):
        result_1 = self.test_class.metrit_basic(1, b=2)
        result_2 = self.test_class.metrit_basic()
        self.assertEqual(result_1, 3)
        self.assertEqual(result_2, 1)

    def test_metrit_basic_no_parenthesis(self):
        result_1 = self.test_class.metrit_basic_no_parenthesis(1, b=2)
        result_2 = self.test_class.metrit_basic_no_parenthesis()
        self.assertEqual(result_1, 3)
        self.assertEqual(result_2, 1)

    def test_metrit_args(self):
        result_1 = self.test_class.test_metrit_args(1, b=2)
        result_2 = self.test_class.test_metrit_args()
        self.assertEqual(result_1, 3)
        self.assertEqual(result_2, 1)

    def test_metrit_static_method(self):
        result_1 = self.test_class.static_method(1, b=2)
        result_2 = self.test_class.static_method()
        self.assertEqual(result_1, 3)
        self.assertEqual(result_2, 1)

    def test_metrit_class_method(self):
        class_name_1, result_1 = self.test_class.class_method(1, b=2)
        class_name_2, result_2 = self.test_class.class_method()
        self.assertEqual(class_name_1, "MetritTestClassDeactivated")
        self.assertEqual(result_1, 3)
        self.assertEqual(class_name_2, "MetritTestClassDeactivated")
        self.assertEqual(result_2, 1)

    def test_metrit_run_from_other_thread(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.test_class.test_metrit_args, 1, b=2)
            result = future.result()

        self.assertEqual(result, 3)

    def test_metrit_run_from_other_process(self):
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.test_class.test_metrit_args, 1, b=2)
            result = future.result()

        self.assertEqual(result, 3)

    def test_metrit_class_method_from_other_thread(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.test_class.class_method, 1, b=2)
            class_name, result = future.result()

        self.assertEqual(class_name, "MetritTestClassDeactivated")
        self.assertEqual(result, 3)

    def test_metrit_class_method_run_from_other_process(self):
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.test_class.class_method, 2, b=6)
            class_name, result = future.result()

        self.assertEqual(class_name, "MetritTestClassDeactivated")
        self.assertEqual(result, 8)

    def test_metrit_static_method_from_other_thread(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.test_class.static_method, 4, b=5)
            result = future.result()

        self.assertEqual(result, 9)

    def test_metrit_static_method_run_from_other_process(self):
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.test_class.static_method, 1, b=2)
            result = future.result()

        self.assertEqual(result, 3)


class TestMetritDeactivated(unittest.TestCase):
    MetritConfig.ACTIVE = False

    def setUp(self):
        MetritConfig.ACTIVE = False

    def test_metrit_basic_deactivated(self):
        @metrit
        def my_function(a: int = 0, b: int = 1):
            return a + b

        self.assertEqual(my_function(1, b=2), 3)
        self.assertEqual(my_function(), 1)

    def test_metrit_with_args_deactivated(self):
        @metrit(verbose=True)
        def my_function(a: int = 0, b: int = 1):
            return a + b

        self.assertEqual(my_function(1, b=2), 3)
        self.assertEqual(my_function(), 1)

    def test_run_from_other_process(self):

        with ProcessPoolExecutor(max_workers=1) as executor:
            future_1 = executor.submit(my_process_function_deactivated, 1, b=2)
            result_1 = future_1.result()
            future_2 = executor.submit(my_process_function_deactivated)
            result_2 = future_2.result()
            future_3 = executor.submit(my_process_function_no_args_deactivated, 1, b=2)
            result_3 = future_3.result()
            future_4 = executor.submit(my_process_function_no_args_deactivated)
            result_4 = future_4.result()

        self.assertEqual(result_1, 3)
        self.assertEqual(result_2, 1)
        self.assertEqual(result_3, 3)
        self.assertEqual(result_4, 1)

    def test_run_from_other_thread(self):
        @metrit()
        def my_thread_function(a=0, b=1):
            return a + b

        @metrit
        def my_thread_no_args_function(a=0, b=1):
            return a + b

        with ThreadPoolExecutor(max_workers=1) as executor:
            future_1 = executor.submit(my_thread_function, 1, b=2)
            result_1 = future_1.result()
            future_2 = executor.submit(my_thread_function)
            result_2 = future_2.result()
            future_3 = executor.submit(my_thread_no_args_function, 1, b=2)
            result_3 = future_3.result()
            future_4 = executor.submit(my_thread_no_args_function)
            result_4 = future_4.result()

        self.assertEqual(result_1, 3)
        self.assertEqual(result_2, 1)
        self.assertEqual(result_3, 3)
        self.assertEqual(result_4, 1)


# Added here since calling a function from another process inside a test method doesn't work
@metrit(find_children=True, isolate=True, verbose=True)
def my_process_function_deactivated(a: int = 0, b: int = 1):
    return a + b


@metrit
def my_process_function_no_args_deactivated(a: int = 0, b: int = 1):
    return a + b


if __name__ == "__main__":
    unittest.main()
