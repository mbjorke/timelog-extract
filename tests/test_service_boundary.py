"""Tests for service boundary option normalization."""

import argparse
import unittest

from timelog_extract import TimelogRunOptions, as_run_options


class ServiceBoundaryTests(unittest.TestCase):
    """Ensures run option conversion supports stable caller contracts."""

    def test_as_run_options_accepts_namespace(self):
        """Converts argparse namespaces into TimelogRunOptions instances."""
        ns = argparse.Namespace(today=True, screen_time="off")
        options = as_run_options(ns)
        self.assertIsInstance(options, TimelogRunOptions)
        self.assertTrue(options.today)
        self.assertEqual(options.screen_time, "off")

    def test_as_run_options_accepts_dict(self):
        """Converts plain dict options into TimelogRunOptions instances."""
        options = as_run_options({"mail_source": "off", "chrome_source": "off"})
        self.assertIsInstance(options, TimelogRunOptions)
        self.assertEqual(options.mail_source, "off")
        self.assertEqual(options.chrome_source, "off")

    def test_as_run_options_rejects_unknown_fields(self):
        """Unknown keys fail fast to surface typos in callers."""
        with self.assertRaises(ValueError) as ctx:
            as_run_options({"mail_source": "off", "unknown_field": "x"})
        self.assertIn("unknown_field", str(ctx.exception))

    def test_as_run_options_preserves_dataclass(self):
        """Returns the same TimelogRunOptions instance when already normalized."""
        original = TimelogRunOptions(today=True)
        converted = as_run_options(original)
        self.assertIs(original, converted)


if __name__ == "__main__":
    unittest.main()
