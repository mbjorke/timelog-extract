from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.cursor import collect_cursor


class CursorNoiseFilterTests(unittest.TestCase):
    def _write_workspace(self, home: Path, wid: str, folder_path: str) -> None:
        ws = (
            home
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "workspaceStorage"
            / wid
        )
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "workspace.json").write_text(
            json.dumps({"folder": f"file://{folder_path}"}),
            encoding="utf-8",
        )

    def _write_log(self, home: Path, rel: str, lines: list[str]) -> None:
        p = home / "Library" / "Application Support" / "Cursor" / "logs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_skips_cursor_diagnostic_noise_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "a" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/ass-membra")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 08:14:12 [error] Error getting submodules: "
                        "A system error occurred (ENOENT: ... workspaceStorage/" + wid + ")"
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "X",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
            self.assertEqual(out, [])

    def test_keeps_non_noise_cursor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "b" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/timelog-extract")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 09:00:00 [info] cursor_agent_exec.startup.workspace_paths "
                        "{\"workspacePathCount\":1} workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Gittan CLI",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "Cursor")
            self.assertEqual(out[0]["project"], "Gittan CLI")

    def test_skips_cursor_git_status_heartbeat_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "c" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 16:32:19 [info] akturo: git_status: true, "
                        "/Users/me/Workspace/Project/akturo workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
            self.assertEqual(out, [])

    def test_lenient_profile_keeps_git_status_heartbeat_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "d" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 16:32:19 [info] akturo: git_status: true, "
                        "/Users/me/Workspace/Project/akturo workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                noise_profile="lenient",
            )
            self.assertEqual(len(out), 1)

    def test_ultra_strict_skips_vscode_diagnostics_executor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "e" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 17:25:46 [info] [VscodeDiagnosticsExecutor] EXECUTE: "
                        "/Users/me/Workspace/Project/akturo/src/index.vue workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                noise_profile="ultra-strict",
            )
            self.assertEqual(out, [])

    def test_strict_keeps_vscode_diagnostics_executor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "f" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 17:25:46 [info] [VscodeDiagnosticsExecutor] EXECUTE: "
                        "/Users/me/Workspace/Project/akturo/src/index.vue workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                noise_profile="strict",
            )
            self.assertEqual(len(out), 1)


class IsCursorDiagnosticNoiseUnitTests(unittest.TestCase):
    """Direct unit tests for _is_cursor_diagnostic_noise()."""

    def setUp(self):
        from collectors.cursor import _is_cursor_diagnostic_noise
        self.fn = _is_cursor_diagnostic_noise

    # --- base markers (all profiles) ---

    def test_base_marker_error_getting_submodules(self):
        line = "2026-04-22 09:00:00 [error] Error getting submodules"
        self.assertTrue(self.fn(line, "lenient"))

    def test_base_marker_enoent(self):
        line = "2026-04-22 09:00:00 [error] ENOENT: no such file"
        self.assertTrue(self.fn(line, "lenient"))

    def test_base_marker_enotempty(self):
        line = "2026-04-22 09:00:00 [error] ENOTEMPTY: directory not empty"
        self.assertTrue(self.fn(line, "lenient"))

    def test_base_marker_file_not_found_git(self):
        line = "2026-04-22 09:00:00 File not found - git:/workspace/project.git"
        self.assertTrue(self.fn(line, "lenient"))

    def test_base_marker_revparse_enoent(self):
        line = "2026-04-22 09:00:00 [git][revparse] Unable to read file: ENOENT"
        self.assertTrue(self.fn(line, "lenient"))

    def test_lenient_allows_non_base_noise(self):
        """Lenient profile should not filter strict markers."""
        line = "2026-04-22 09:00:00 [info] git_status: true, candidate index"
        self.assertFalse(self.fn(line, "lenient"))

    # --- strict markers ---

    def test_strict_filters_git_status_true(self):
        line = "2026-04-22 09:00:00 [info] git_status: true"
        self.assertTrue(self.fn(line, "strict"))

    def test_strict_filters_git_status_false(self):
        line = "2026-04-22 09:00:00 [info] git_status: false"
        self.assertTrue(self.fn(line, "strict"))

    def test_strict_filters_candidate_index(self):
        line = "2026-04-22 09:00:00 [info] candidate index computed"
        self.assertTrue(self.fn(line, "strict"))

    def test_strict_filters_cursorignore_filesearch(self):
        line = "2026-04-22 09:00:00 [info] ExtHostSearch [CursorIgnore] internal FileSearch start"
        self.assertTrue(self.fn(line, "strict"))

    def test_strict_does_not_filter_ultra_strict_markers(self):
        """Strict profile should not filter ultra-strict only markers."""
        line = "2026-04-22 09:00:00 [info] bootstrapping repository index at /Users/me/repo"
        self.assertFalse(self.fn(line, "strict"))

    # --- ultra-strict markers ---

    def test_ultra_strict_filters_workspace_paths(self):
        line = "2026-04-22 09:00:00 [info] cursor_agent_exec.startup.workspace_paths {}"
        self.assertTrue(self.fn(line, "ultra-strict"))

    def test_ultra_strict_filters_opened_repository(self):
        line = "2026-04-22 09:00:00 [info] [model][openRepository] Opened repository at path"
        self.assertTrue(self.fn(line, "ultra-strict"))

    def test_ultra_strict_filters_bootstrapping_repository(self):
        line = "2026-04-22 09:00:00 [info] bootstrapping repository index at /Users/me/project"
        self.assertTrue(self.fn(line, "ultra-strict"))

    def test_ultra_strict_filters_skipping_lock(self):
        line = "2026-04-22 09:00:00 [info] skipping acquiring lock for existing run"
        self.assertTrue(self.fn(line, "ultra-strict"))

    def test_ultra_strict_filters_vscodediagnosticsexecutor(self):
        line = "2026-04-22 09:00:00 [info] [VscodeDiagnosticsExecutor] execute: some task"
        self.assertTrue(self.fn(line, "ultra-strict"))

    def test_ultra_strict_filters_git_git_dir_command(self):
        line = "2026-04-22 09:00:00 [info] > git --git-dir /Users/me/.git log"
        self.assertTrue(self.fn(line, "ultra-strict"))

    def test_ultra_strict_also_filters_strict_markers(self):
        """Ultra-strict must also filter strict-profile markers."""
        line = "2026-04-22 09:00:00 [info] git_status: true"
        self.assertTrue(self.fn(line, "ultra-strict"))

    def test_ultra_strict_also_filters_base_markers(self):
        """Ultra-strict must also filter base-profile markers."""
        line = "2026-04-22 09:00:00 [error] enoent: something"
        self.assertTrue(self.fn(line, "ultra-strict"))

    # --- edge cases ---

    def test_none_line_does_not_crash(self):
        """None input should be handled gracefully."""
        # None is passed as first arg despite str type hint
        self.assertFalse(self.fn(None, "strict"))  # type: ignore[arg-type]

    def test_empty_line_is_not_noise(self):
        self.assertFalse(self.fn("", "strict"))

    def test_unknown_noise_profile_only_applies_base_markers(self):
        """An unknown profile name uses only base markers (not strict or ultra-strict)."""
        # git_status: true is a strict-only marker; unknown profile should NOT filter it
        line = "2026-04-22 09:00:00 [info] git_status: true"
        self.assertFalse(self.fn(line, "unknown-profile"))

    def test_unknown_noise_profile_still_filters_base_markers(self):
        """Even unknown profiles filter the base markers."""
        line = "2026-04-22 09:00:00 [error] ENOENT: no such file"
        self.assertTrue(self.fn(line, "unknown-profile"))

    def test_case_insensitive_matching(self):
        """Markers are matched case-insensitively."""
        line = "2026-04-22 09:00:00 [ERROR] ENOENT: file missing"
        self.assertTrue(self.fn(line, "strict"))


if __name__ == "__main__":
    unittest.main()