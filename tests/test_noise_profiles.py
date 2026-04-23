"""Tests for core/noise_profiles.py constants and membership."""

import unittest

from core.noise_profiles import (
    DEFAULT_LOVABLE_NOISE_PROFILE,
    DEFAULT_NOISE_PROFILE,
    LOVABLE_NOISE_PROFILES,
    NOISE_PROFILES,
)


class NoiseProfileConstantsTests(unittest.TestCase):
    """Verify canonical defaults and valid-profile sets are correct."""

    def test_default_noise_profile_is_strict(self):
        self.assertEqual(DEFAULT_NOISE_PROFILE, "strict")

    def test_default_lovable_noise_profile_is_balanced(self):
        self.assertEqual(DEFAULT_LOVABLE_NOISE_PROFILE, "balanced")

    def test_noise_profiles_contains_expected_values(self):
        self.assertIn("lenient", NOISE_PROFILES)
        self.assertIn("strict", NOISE_PROFILES)
        self.assertIn("ultra-strict", NOISE_PROFILES)

    def test_noise_profiles_does_not_contain_unknown(self):
        self.assertNotIn("normal", NOISE_PROFILES)
        self.assertNotIn("balanced", NOISE_PROFILES)
        self.assertNotIn("", NOISE_PROFILES)

    def test_lovable_noise_profiles_contains_expected_values(self):
        self.assertIn("normal", LOVABLE_NOISE_PROFILES)
        self.assertIn("balanced", LOVABLE_NOISE_PROFILES)
        self.assertIn("strict", LOVABLE_NOISE_PROFILES)

    def test_lovable_noise_profiles_does_not_contain_global_only(self):
        self.assertNotIn("lenient", LOVABLE_NOISE_PROFILES)
        self.assertNotIn("ultra-strict", LOVABLE_NOISE_PROFILES)

    def test_default_noise_profile_is_in_noise_profiles(self):
        self.assertIn(DEFAULT_NOISE_PROFILE, NOISE_PROFILES)

    def test_default_lovable_noise_profile_is_in_lovable_noise_profiles(self):
        self.assertIn(DEFAULT_LOVABLE_NOISE_PROFILE, LOVABLE_NOISE_PROFILES)

    def test_noise_profiles_is_a_set(self):
        self.assertIsInstance(NOISE_PROFILES, set)

    def test_lovable_noise_profiles_is_a_set(self):
        self.assertIsInstance(LOVABLE_NOISE_PROFILES, set)


if __name__ == "__main__":
    unittest.main()