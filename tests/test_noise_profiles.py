"""Tests for core/noise_profiles.py constants and defaults."""

from __future__ import annotations

import unittest

from core.noise_profiles import (
    DEFAULT_LOVABLE_NOISE_PROFILE,
    DEFAULT_NOISE_PROFILE,
    LOVABLE_NOISE_PROFILES,
    NOISE_PROFILES,
)


class NoiseProfileConstantsTests(unittest.TestCase):
    """Verify canonical noise profile names and defaults are correct."""

    def test_default_noise_profile_is_strict(self):
        self.assertEqual(DEFAULT_NOISE_PROFILE, "strict")

    def test_default_lovable_noise_profile_is_balanced(self):
        self.assertEqual(DEFAULT_LOVABLE_NOISE_PROFILE, "balanced")

    def test_noise_profiles_contains_lenient(self):
        self.assertIn("lenient", NOISE_PROFILES)

    def test_noise_profiles_contains_strict(self):
        self.assertIn("strict", NOISE_PROFILES)

    def test_noise_profiles_contains_ultra_strict(self):
        self.assertIn("ultra-strict", NOISE_PROFILES)

    def test_noise_profiles_has_exactly_three_entries(self):
        self.assertEqual(len(NOISE_PROFILES), 3)

    def test_lovable_noise_profiles_contains_normal(self):
        self.assertIn("normal", LOVABLE_NOISE_PROFILES)

    def test_lovable_noise_profiles_contains_balanced(self):
        self.assertIn("balanced", LOVABLE_NOISE_PROFILES)

    def test_lovable_noise_profiles_contains_strict(self):
        self.assertIn("strict", LOVABLE_NOISE_PROFILES)

    def test_lovable_noise_profiles_has_exactly_three_entries(self):
        self.assertEqual(len(LOVABLE_NOISE_PROFILES), 3)

    def test_default_noise_profile_is_in_valid_set(self):
        self.assertIn(DEFAULT_NOISE_PROFILE, NOISE_PROFILES)

    def test_default_lovable_noise_profile_is_in_valid_set(self):
        self.assertIn(DEFAULT_LOVABLE_NOISE_PROFILE, LOVABLE_NOISE_PROFILES)

    def test_noise_profiles_are_all_lowercase(self):
        for profile in NOISE_PROFILES:
            self.assertEqual(profile, profile.lower(), msg=f"Profile not lowercase: {profile!r}")

    def test_lovable_noise_profiles_are_all_lowercase(self):
        for profile in LOVABLE_NOISE_PROFILES:
            self.assertEqual(profile, profile.lower(), msg=f"Profile not lowercase: {profile!r}")

    def test_profiles_are_strings(self):
        for p in NOISE_PROFILES:
            self.assertIsInstance(p, str)
        for p in LOVABLE_NOISE_PROFILES:
            self.assertIsInstance(p, str)


if __name__ == "__main__":
    unittest.main()