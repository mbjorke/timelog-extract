"""Unit tests for _is_cursor_diagnostic_noise in collectors/cursor.py."""

import unittest

from collectors.cursor import _is_cursor_diagnostic_noise


class CursorDiagnosticNoiseTests(unittest.TestCase):
    """Tests for the noise-filtering predicate added in this PR."""

    # --- base markers (all profiles) ---

    def test_base_marker_error_getting_submodules(self):
        """Base marker matched across all profiles."""
        line = "2026-01-01 10:00:00 Error getting submodules for repo"
        self.assertTrue(_is_cursor_diagnostic_noise(line, "lenient"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_base_marker_enoent(self):
        """[error] enoent is matched regardless of profile."""
        line = "[error] ENOENT: no such file or directory"
        self.assertTrue(_is_cursor_diagnostic_noise(line, "lenient"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "strict"))

    def test_base_marker_enotempty(self):
        """[error] enotempty is a base marker."""
        self.assertTrue(_is_cursor_diagnostic_noise("[error] enotempty foo", "lenient"))

    def test_base_marker_file_not_found_git(self):
        """file not found - git:/ is a base marker."""
        self.assertTrue(_is_cursor_diagnostic_noise("file not found - git:/repo/file.ts", "lenient"))

    def test_base_marker_revparse_enoent(self):
        """[git][revparse] unable to read file: enoent is a base marker."""
        self.assertTrue(_is_cursor_diagnostic_noise("[git][revparse] unable to read file: enoent", "lenient"))

    # --- strict markers ---

    def test_strict_marker_git_status_true_filtered_in_strict(self):
        """git_status: true is filtered in strict but not lenient."""
        line = "2026-01-01 10:00:00 git_status: true for workspace"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "lenient"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_strict_marker_git_status_false(self):
        """git_status: false is a strict marker."""
        line = "git_status: false"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "lenient"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "strict"))

    def test_strict_marker_candidate_index(self):
        """'candidate index' is a strict marker."""
        line = "scoring candidate index 42 in ranking"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "lenient"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "strict"))

    def test_strict_marker_exthostsearch(self):
        """exthostsearch cursorignore filesearch is a strict marker."""
        line = "exthostsearch [cursorignore] internal filesearch start at path"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "lenient"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "strict"))

    # --- ultra-strict markers ---

    def test_ultra_strict_marker_startup_workspace_paths(self):
        """cursor_agent_exec.startup.workspace_paths is ultra-strict only."""
        line = "cursor_agent_exec.startup.workspace_paths=[/home/user/proj]"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "lenient"))
        self.assertFalse(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_ultra_strict_marker_openrepository(self):
        """[model][openrepository] opened repository is ultra-strict only."""
        line = "[model][openrepository] opened repository at /Users/dev/myrepo"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_ultra_strict_marker_bootstrapping_repository(self):
        """bootstrapping repository index is ultra-strict only."""
        line = "bootstrapping repository index at /Users/dev/project"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_ultra_strict_marker_skipping_acquiring_lock(self):
        """skipping acquiring lock is ultra-strict only."""
        line = "skipping acquiring lock for lockfile"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_ultra_strict_marker_vscodediagnosticsexecutor(self):
        """[vscodediagnosticsexecutor] execute: is ultra-strict only."""
        line = "[vscodediagnosticsexecutor] execute: some command"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_ultra_strict_marker_git_git_dir(self):
        """> git --git-dir is ultra-strict only."""
        line = "> git --git-dir /home/user/.git rev-parse HEAD"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertTrue(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    # --- non-noise lines should pass through ---

    def test_real_work_line_not_filtered(self):
        """Regular work activity lines are not filtered."""
        line = "2026-01-01 10:00:00 User opened file /Users/dev/project/src/main.ts"
        self.assertFalse(_is_cursor_diagnostic_noise(line, "strict"))
        self.assertFalse(_is_cursor_diagnostic_noise(line, "ultra-strict"))

    def test_empty_line_returns_false(self):
        """Empty string is not noise."""
        self.assertFalse(_is_cursor_diagnostic_noise("", "strict"))

    def test_none_line_returns_false(self):
        """None input is handled gracefully and not treated as noise."""
        self.assertFalse(_is_cursor_diagnostic_noise(None, "strict"))

    # --- case insensitivity ---

    def test_base_markers_case_insensitive(self):
        """Base markers are matched case-insensitively."""
        self.assertTrue(_is_cursor_diagnostic_noise("ERROR GETTING SUBMODULES", "lenient"))
        self.assertTrue(_is_cursor_diagnostic_noise("[ERROR] ENOENT file missing", "lenient"))

    # --- default profile fallback ---

    def test_default_profile_is_strict(self):
        """When no profile is passed, default is 'strict'."""
        # git_status: true is a strict-only marker
        line = "git_status: true"
        self.assertTrue(_is_cursor_diagnostic_noise(line))

    def test_none_profile_falls_back_to_strict(self):
        """None profile falls back to strict behavior."""
        line = "git_status: false"
        self.assertTrue(_is_cursor_diagnostic_noise(line, None))

    def test_unknown_profile_falls_back_to_strict(self):
        """Unknown profile string treated as strict."""
        # base markers should still match; strict markers should too since unknown -> strict
        line = "error getting submodules"
        self.assertTrue(_is_cursor_diagnostic_noise(line, "unknown-profile"))

    # --- boundary / regression ---

    def test_ultra_strict_includes_strict_markers_too(self):
        """ultra-strict profile includes both strict and base markers."""
        self.assertTrue(_is_cursor_diagnostic_noise("git_status: true", "ultra-strict"))
        self.assertTrue(_is_cursor_diagnostic_noise("[error] enoent", "ultra-strict"))
        self.assertTrue(_is_cursor_diagnostic_noise("cursor_agent_exec.startup.workspace_paths=[]", "ultra-strict"))

    def test_lenient_only_has_base_markers(self):
        """lenient profile only filters base markers; strict-only terms pass through."""
        self.assertFalse(_is_cursor_diagnostic_noise("git_status: true", "lenient"))
        self.assertFalse(_is_cursor_diagnostic_noise("candidate index", "lenient"))
        self.assertFalse(_is_cursor_diagnostic_noise("cursor_agent_exec.startup.workspace_paths=[]", "lenient"))
        # but base markers are still filtered
        self.assertTrue(_is_cursor_diagnostic_noise("[error] enoent: missing", "lenient"))


if __name__ == "__main__":
    unittest.main()