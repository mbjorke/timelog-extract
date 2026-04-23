"""Tests for new fields added to TimelogRunOptions in core/cli_options.py."""

import unittest

from core.cli_options import TimelogRunOptions
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE


class TimelogRunOptionsNewFieldsTests(unittest.TestCase):
    """Verify new default field values on TimelogRunOptions dataclass."""

    def _make_default(self):
        return TimelogRunOptions()

    def test_noise_profile_default_is_strict(self):
        opts = self._make_default()
        self.assertEqual(opts.noise_profile, DEFAULT_NOISE_PROFILE)
        self.assertEqual(opts.noise_profile, "strict")

    def test_lovable_noise_profile_default_is_balanced(self):
        opts = self._make_default()
        self.assertEqual(opts.lovable_noise_profile, DEFAULT_LOVABLE_NOISE_PROFILE)
        self.assertEqual(opts.lovable_noise_profile, "balanced")

    def test_additive_summary_default_is_false(self):
        opts = self._make_default()
        self.assertFalse(opts.additive_summary)

    def test_invoice_mode_default_is_baseline(self):
        opts = self._make_default()
        self.assertEqual(opts.invoice_mode, "baseline")

    def test_invoice_ground_truth_default_is_none(self):
        opts = self._make_default()
        self.assertIsNone(opts.invoice_ground_truth)

    def test_custom_noise_profile_assigned(self):
        opts = TimelogRunOptions(noise_profile="ultra-strict")
        self.assertEqual(opts.noise_profile, "ultra-strict")

    def test_custom_lovable_noise_profile_assigned(self):
        opts = TimelogRunOptions(lovable_noise_profile="strict")
        self.assertEqual(opts.lovable_noise_profile, "strict")

    def test_additive_summary_can_be_set(self):
        opts = TimelogRunOptions(additive_summary=True)
        self.assertTrue(opts.additive_summary)

    def test_invoice_mode_can_be_set(self):
        opts = TimelogRunOptions(invoice_mode="calibrated-a")
        self.assertEqual(opts.invoice_mode, "calibrated-a")

    def test_invoice_ground_truth_can_be_set(self):
        opts = TimelogRunOptions(invoice_ground_truth="/path/to/truth.json")
        self.assertEqual(opts.invoice_ground_truth, "/path/to/truth.json")

    def test_all_new_fields_independently_settable(self):
        opts = TimelogRunOptions(
            noise_profile="lenient",
            lovable_noise_profile="normal",
            additive_summary=True,
            invoice_mode="calibrated-a",
            invoice_ground_truth="/truth.json",
        )
        self.assertEqual(opts.noise_profile, "lenient")
        self.assertEqual(opts.lovable_noise_profile, "normal")
        self.assertTrue(opts.additive_summary)
        self.assertEqual(opts.invoice_mode, "calibrated-a")
        self.assertEqual(opts.invoice_ground_truth, "/truth.json")


if __name__ == "__main__":
    unittest.main()