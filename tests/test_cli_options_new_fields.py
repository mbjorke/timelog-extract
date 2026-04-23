"""Tests for new fields added to TimelogRunOptions in this PR."""

from __future__ import annotations

import unittest

from core.cli_options import TimelogRunOptions, as_run_options
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE


class TimelogRunOptionsNewFieldsTests(unittest.TestCase):
    """Verify new fields in TimelogRunOptions have correct defaults and behavior."""

    def test_additive_summary_default_is_false(self):
        opts = TimelogRunOptions()
        self.assertFalse(opts.additive_summary)

    def test_noise_profile_default_matches_constant(self):
        opts = TimelogRunOptions()
        self.assertEqual(opts.noise_profile, DEFAULT_NOISE_PROFILE)
        self.assertEqual(opts.noise_profile, "strict")

    def test_lovable_noise_profile_default_matches_constant(self):
        opts = TimelogRunOptions()
        self.assertEqual(opts.lovable_noise_profile, DEFAULT_LOVABLE_NOISE_PROFILE)
        self.assertEqual(opts.lovable_noise_profile, "balanced")

    def test_invoice_mode_default_is_baseline(self):
        opts = TimelogRunOptions()
        self.assertEqual(opts.invoice_mode, "baseline")

    def test_invoice_ground_truth_default_is_none(self):
        opts = TimelogRunOptions()
        self.assertIsNone(opts.invoice_ground_truth)

    def test_can_set_additive_summary_true(self):
        opts = TimelogRunOptions(additive_summary=True)
        self.assertTrue(opts.additive_summary)

    def test_can_set_noise_profile_to_lenient(self):
        opts = TimelogRunOptions(noise_profile="lenient")
        self.assertEqual(opts.noise_profile, "lenient")

    def test_can_set_noise_profile_to_ultra_strict(self):
        opts = TimelogRunOptions(noise_profile="ultra-strict")
        self.assertEqual(opts.noise_profile, "ultra-strict")

    def test_can_set_lovable_noise_profile_to_strict(self):
        opts = TimelogRunOptions(lovable_noise_profile="strict")
        self.assertEqual(opts.lovable_noise_profile, "strict")

    def test_can_set_lovable_noise_profile_to_normal(self):
        opts = TimelogRunOptions(lovable_noise_profile="normal")
        self.assertEqual(opts.lovable_noise_profile, "normal")

    def test_can_set_invoice_mode_to_calibrated_a(self):
        opts = TimelogRunOptions(invoice_mode="calibrated-a")
        self.assertEqual(opts.invoice_mode, "calibrated-a")

    def test_can_set_invoice_ground_truth(self):
        opts = TimelogRunOptions(invoice_ground_truth="path/to/truth.json")
        self.assertEqual(opts.invoice_ground_truth, "path/to/truth.json")


class AsRunOptionsNewFieldsTests(unittest.TestCase):
    """Verify as_run_options() normalizes new fields from dict and argparse.Namespace."""

    def test_as_run_options_from_dict_with_additive_summary(self):
        opts = as_run_options({"additive_summary": True})
        self.assertTrue(opts.additive_summary)

    def test_as_run_options_from_dict_with_noise_profile(self):
        opts = as_run_options({"noise_profile": "ultra-strict"})
        self.assertEqual(opts.noise_profile, "ultra-strict")

    def test_as_run_options_from_dict_with_lovable_noise_profile(self):
        opts = as_run_options({"lovable_noise_profile": "strict"})
        self.assertEqual(opts.lovable_noise_profile, "strict")

    def test_as_run_options_from_dict_with_invoice_mode(self):
        opts = as_run_options({"invoice_mode": "calibrated-a"})
        self.assertEqual(opts.invoice_mode, "calibrated-a")

    def test_as_run_options_from_dict_with_invoice_ground_truth(self):
        opts = as_run_options({"invoice_ground_truth": "/some/path.json"})
        self.assertEqual(opts.invoice_ground_truth, "/some/path.json")

    def test_as_run_options_passthrough_when_already_timelog_run_options(self):
        original = TimelogRunOptions(noise_profile="lenient", additive_summary=True)
        result = as_run_options(original)
        self.assertIs(result, original)

    def test_as_run_options_unknown_key_raises_value_error(self):
        with self.assertRaises(ValueError):
            as_run_options({"unknown_field_xyz": True})

    def test_new_fields_present_in_dataclass_fields(self):
        fields = set(TimelogRunOptions.__dataclass_fields__.keys())
        for field in ("additive_summary", "noise_profile", "lovable_noise_profile", "invoice_mode", "invoice_ground_truth"):
            self.assertIn(field, fields, msg=f"Expected field '{field}' in TimelogRunOptions")


if __name__ == "__main__":
    unittest.main()