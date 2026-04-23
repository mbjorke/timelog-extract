"""Unit tests for core/noise_profiles.py constants."""

import unittest

from core.noise_profiles import (
    DEFAULT_LOVABLE_NOISE_PROFILE,
    DEFAULT_NOISE_PROFILE,
    LOVABLE_NOISE_PROFILES,
    NOISE_PROFILES,
)


class NoiseProfileConstantsTests(unittest.TestCase):
    """Verify canonical noise profile names and defaults."""

    def test_default_noise_profile_is_strict(self):
        """DEFAULT_NOISE_PROFILE must be 'strict'."""
        self.assertEqual(DEFAULT_NOISE_PROFILE, "strict")

    def test_default_lovable_noise_profile_is_balanced(self):
        """DEFAULT_LOVABLE_NOISE_PROFILE must be 'balanced'."""
        self.assertEqual(DEFAULT_LOVABLE_NOISE_PROFILE, "balanced")

    def test_noise_profiles_contains_expected_values(self):
        """NOISE_PROFILES contains lenient, strict, ultra-strict."""
        self.assertIn("lenient", NOISE_PROFILES)
        self.assertIn("strict", NOISE_PROFILES)
        self.assertIn("ultra-strict", NOISE_PROFILES)

    def test_lovable_noise_profiles_contains_expected_values(self):
        """LOVABLE_NOISE_PROFILES contains normal, balanced, strict."""
        self.assertIn("normal", LOVABLE_NOISE_PROFILES)
        self.assertIn("balanced", LOVABLE_NOISE_PROFILES)
        self.assertIn("strict", LOVABLE_NOISE_PROFILES)

    def test_default_noise_profile_is_in_noise_profiles_set(self):
        """The default global profile is a member of the valid set."""
        self.assertIn(DEFAULT_NOISE_PROFILE, NOISE_PROFILES)

    def test_default_lovable_profile_is_in_lovable_profiles_set(self):
        """The default lovable profile is a member of the valid set."""
        self.assertIn(DEFAULT_LOVABLE_NOISE_PROFILE, LOVABLE_NOISE_PROFILES)

    def test_noise_profiles_is_a_set(self):
        """NOISE_PROFILES is a set (no duplicates)."""
        self.assertIsInstance(NOISE_PROFILES, set)

    def test_lovable_noise_profiles_is_a_set(self):
        """LOVABLE_NOISE_PROFILES is a set (no duplicates)."""
        self.assertIsInstance(LOVABLE_NOISE_PROFILES, set)

    def test_noise_profiles_has_exactly_three_entries(self):
        """NOISE_PROFILES has exactly three entries."""
        self.assertEqual(len(NOISE_PROFILES), 3)

    def test_lovable_noise_profiles_has_exactly_three_entries(self):
        """LOVABLE_NOISE_PROFILES has exactly three entries."""
        self.assertEqual(len(LOVABLE_NOISE_PROFILES), 3)


if __name__ == "__main__":
    unittest.main()