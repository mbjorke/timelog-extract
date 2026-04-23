"""Tests for _is_cursor_diagnostic_noise() in collectors/cursor.py."""

import unittest

from collectors.cursor import _is_cursor_diagnostic_noise


class CursorDiagnosticNoiseBaseMarkersTests(unittest.TestCase):
    """Base markers are filtered regardless of noise profile."""

    BASE_MARKER_LINES = [
        "2026-04-01 10:00:00 error getting submodules for repo xyz",
        "2026-04-01 10:00:00 [Error] ENOENT: no such file",
        "2026-04-01 10:00:00 [Error] ENOTEMPTY: directory not empty",
        "2026-04-01 10:00:00 File not found - git:/Users/dev/project",
        "2026-04-01 10:00:00 [git][RevParse] Unable to read file: ENOENT /path",
    ]

    def test_base_markers_filtered_in_lenient(self):
        for line in self.BASE_MARKER_LINES:
            with self.subTest(line=line):
                self.assertTrue(
                    _is_cursor_diagnostic_noise(line, noise_profile="lenient"),
                    f"Expected noise in lenient profile: {line!r}",
                )

    def test_base_markers_filtered_in_strict(self):
        for line in self.BASE_MARKER_LINES:
            with self.subTest(line=line):
                self.assertTrue(
                    _is_cursor_diagnostic_noise(line, noise_profile="strict"),
                )

    def test_base_markers_filtered_in_ultra_strict(self):
        for line in self.BASE_MARKER_LINES:
            with self.subTest(line=line):
                self.assertTrue(
                    _is_cursor_diagnostic_noise(line, noise_profile="ultra-strict"),
                )


class CursorDiagnosticNoiseStrictMarkersTests(unittest.TestCase):
    """Strict markers are filtered in strict and ultra-strict, but NOT lenient."""

    STRICT_MARKER_LINES = [
        "2026-04-01 10:00:00 git_status: true",
        "2026-04-01 10:00:00 git_status: false",
        "2026-04-01 10:00:00 candidate index updated",
        "2026-04-01 10:00:00 extHostSearch [CursorIgnore] internal filesearch start",
    ]

    def test_strict_markers_not_filtered_in_lenient(self):
        for line in self.STRICT_MARKER_LINES:
            with self.subTest(line=line):
                self.assertFalse(
                    _is_cursor_diagnostic_noise(line, noise_profile="lenient"),
                    f"Should NOT filter in lenient profile: {line!r}",
                )

    def test_strict_markers_filtered_in_strict(self):
        for line in self.STRICT_MARKER_LINES:
            with self.subTest(line=line):
                self.assertTrue(
                    _is_cursor_diagnostic_noise(line, noise_profile="strict"),
                )

    def test_strict_markers_filtered_in_ultra_strict(self):
        for line in self.STRICT_MARKER_LINES:
            with self.subTest(line=line):
                self.assertTrue(
                    _is_cursor_diagnostic_noise(line, noise_profile="ultra-strict"),
                )


class CursorDiagnosticNoiseUltraStrictMarkersTests(unittest.TestCase):
    """Ultra-strict markers are ONLY filtered in ultra-strict."""

    ULTRA_STRICT_LINES = [
        "2026-04-01 10:00:00 cursor_agent_exec.startup.workspace_paths: /Users/dev",
        "2026-04-01 10:00:00 [model][openRepository] Opened repository /Users/dev/repo",
        "2026-04-01 10:00:00 Bootstrapping repository index at /Users/dev/repo",
        "2026-04-01 10:00:00 Skipping acquiring lock for workspace",
        "2026-04-01 10:00:00 [vscodeDiagnosticsExecutor] execute: tsc",
        "2026-04-01 10:00:00 > git --git-dir /Users/dev/repo/.git status",
    ]

    def test_ultra_strict_markers_not_filtered_in_lenient(self):
        for line in self.ULTRA_STRICT_LINES:
            with self.subTest(line=line):
                self.assertFalse(
                    _is_cursor_diagnostic_noise(line, noise_profile="lenient"),
                )

    def test_ultra_strict_markers_not_filtered_in_strict(self):
        for line in self.ULTRA_STRICT_LINES:
            with self.subTest(line=line):
                self.assertFalse(
                    _is_cursor_diagnostic_noise(line, noise_profile="strict"),
                )

    def test_ultra_strict_markers_filtered_in_ultra_strict(self):
        for line in self.ULTRA_STRICT_LINES:
            with self.subTest(line=line):
                self.assertTrue(
                    _is_cursor_diagnostic_noise(line, noise_profile="ultra-strict"),
                )


class CursorDiagnosticNoiseEdgeCasesTests(unittest.TestCase):
    """Edge cases and boundary behavior."""

    def test_empty_string_is_not_noise(self):
        self.assertFalse(_is_cursor_diagnostic_noise("", noise_profile="strict"))

    def test_none_input_is_not_noise(self):
        self.assertFalse(_is_cursor_diagnostic_noise(None, noise_profile="strict"))

    def test_normal_log_line_is_not_noise(self):
        line = "2026-04-01 10:00:00 User saved file /Users/dev/project/main.py"
        self.assertFalse(_is_cursor_diagnostic_noise(line, noise_profile="ultra-strict"))

    def test_case_insensitive_matching(self):
        line = "2026-04-01 10:00:00 ERROR GETTING SUBMODULES for repo"
        self.assertTrue(_is_cursor_diagnostic_noise(line, noise_profile="lenient"))

    def test_default_profile_is_strict(self):
        # git_status should be filtered by default (strict is default)
        line = "2026-04-01 10:00:00 git_status: true"
        self.assertTrue(_is_cursor_diagnostic_noise(line))

    def test_unknown_profile_uses_only_base_markers(self):
        # Unknown profiles don't match {"strict", "ultra-strict"}, so only base_markers apply.
        # Strict-only markers (e.g. git_status) are NOT filtered for unknown profiles.
        strict_line = "2026-04-01 10:00:00 git_status: true"
        self.assertFalse(
            _is_cursor_diagnostic_noise(strict_line, noise_profile="unknown-profile")
        )
        # But base markers ARE still filtered even for unknown profiles.
        base_line = "2026-04-01 10:00:00 error getting submodules for repo"
        self.assertTrue(
            _is_cursor_diagnostic_noise(base_line, noise_profile="unknown-profile")
        )

    def test_none_profile_treated_as_strict(self):
        # None is coerced to "strict" via `(noise_profile or "strict")`
        strict_line = "2026-04-01 10:00:00 git_status: false"
        self.assertTrue(_is_cursor_diagnostic_noise(strict_line, noise_profile=None))

    def test_real_coding_activity_not_filtered_any_profile(self):
        """A genuine coding event should never be classified as noise."""
        coding_line = "2026-04-01 10:00:00 User accepted AI suggestion in /Users/dev/app/main.py"
        for profile in ("lenient", "strict", "ultra-strict"):
            with self.subTest(profile=profile):
                self.assertFalse(
                    _is_cursor_diagnostic_noise(coding_line, noise_profile=profile)
                )

    def test_partial_marker_match_in_longer_line(self):
        """Marker embedded in longer line is still detected."""
        line = "2026-04-01 10:00:00 INFO: [git][revparse] unable to read file: enoent at path xyz"
        self.assertTrue(_is_cursor_diagnostic_noise(line, noise_profile="strict"))

    def test_whitespace_only_profile_uses_only_base_markers(self):
        # "   ".strip() == "" which doesn't match "strict" or "ultra-strict",
        # so only base_markers apply (same as lenient behavior).
        strict_only_line = "2026-04-01 10:00:00 git_status: true"
        self.assertFalse(_is_cursor_diagnostic_noise(strict_only_line, noise_profile="   "))
        base_line = "2026-04-01 10:00:00 error getting submodules for repo"
        self.assertTrue(_is_cursor_diagnostic_noise(base_line, noise_profile="   "))


if __name__ == "__main__":
    unittest.main()