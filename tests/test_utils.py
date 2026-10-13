import unittest

from metrit.utils import extract_callable_and_args_if_method, format_size


class Sample:
    def method(self, value):
        return value

    @staticmethod
    def static_method(value):
        return value

    @classmethod
    def class_method(cls, value):
        return value


class TestExtractCallableAndArgs(unittest.TestCase):
    def test_plain_function_is_not_a_method(self):
        callable_func, args, args_to_print, is_method = extract_callable_and_args_if_method(Sample.method, "x", 5)

        self.assertIs(callable_func, Sample.method)
        self.assertEqual(args, ("x", 5))
        self.assertEqual(args_to_print, ("x", 5))
        self.assertFalse(is_method)

    def test_instance_method_drops_self(self):
        instance = Sample()
        callable_func, args, args_to_print, is_method = extract_callable_and_args_if_method(Sample.method, instance, 5)

        self.assertIs(callable_func, Sample.method)
        self.assertEqual(args, (instance, 5))
        self.assertEqual(args_to_print, (5,))
        self.assertTrue(is_method)

    def test_staticmethod_drops_instance(self):
        instance = Sample()
        static = Sample.__dict__["static_method"]
        callable_func, args, args_to_print, is_method = extract_callable_and_args_if_method(static, instance, 5)

        self.assertIs(callable_func, static)
        self.assertEqual(args, (5,))
        self.assertEqual(args_to_print, (5,))
        self.assertTrue(is_method)

    def test_classmethod_binds_class(self):
        instance = Sample()
        class_method = Sample.__dict__["class_method"]
        callable_func, args, args_to_print, is_method = extract_callable_and_args_if_method(class_method, instance, 5)

        self.assertIs(callable_func, class_method.__func__)
        self.assertEqual(args, (Sample, 5))
        self.assertEqual(args_to_print, (5,))
        self.assertTrue(is_method)


class TestFormatSize(unittest.TestCase):

    def test_bytes(self):
        self.assertEqual(format_size(10), "10B")

    def test_kilobytes(self):
        self.assertEqual(format_size(1024), "1.00KB")

    def test_megabytes(self):
        self.assertEqual(format_size(1024 * 1024), "1.00MB")

    def test_gigabytes(self):
        self.assertEqual(format_size(1024 * 1024 * 1024), "1.00GB")

    def test_terabytes(self):
        self.assertEqual(format_size(1024 * 1024 * 1024 * 1024), "1.00TB")

    def test_petabytes(self):
        self.assertEqual(format_size(1024 * 1024 * 1024 * 1024 * 1024), "1.00PB")


if __name__ == "__main__":
    unittest.main()
