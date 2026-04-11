"""Unit tests for core.cli_options.split_comma_separated_list (project wizard / safe CSV)."""

import unittest

from core.cli_options import split_comma_separated_list


class SplitCommaSeparatedTests(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(split_comma_separated_list(None), [])

    def test_empty_and_whitespace_returns_empty(self):
        self.assertEqual(split_comma_separated_list(""), [])
        self.assertEqual(split_comma_separated_list("   "), [])
        self.assertEqual(split_comma_separated_list("\t\n"), [])

    def test_splits_and_strips(self):
        self.assertEqual(
            split_comma_separated_list("alpha, beta, gamma"),
            ["alpha", "beta", "gamma"],
        )
        self.assertEqual(
            split_comma_separated_list(" foo , bar "),
            ["foo", "bar"],
        )

    def test_skips_empty_segments(self):
        self.assertEqual(
            split_comma_separated_list("a,,b, ,c"),
            ["a", "b", "c"],
        )


if __name__ == "__main__":
    unittest.main()
