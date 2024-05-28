import unittest

from metrit.utils import format_size


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
