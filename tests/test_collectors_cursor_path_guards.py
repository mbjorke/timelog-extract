"""Cursor path guards: Application Support truncation + IDE metadata trees."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.cursor import collect_cursor
from tests.event_helpers import make_test_event


class CursorPathGuardTests(unittest.TestCase):
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

    def _collect(self, home: Path):
        return collect_cursor(
            profiles=[],
            dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
            dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
            home=home,
            local_tz=timezone.utc,
            classify_project=lambda _hay, _profiles: "X",
            make_event=make_test_event,
        )

    def test_skips_truncated_application_support_path(self):
        # Regression: space in "Application Support" truncates the /Users/...
        # extractor → dir=application and a nonsense map prompt.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:00:00 [info] Reloading configuration "
                    "/Users/me/Library/Application Support/Cursor/logs/skills"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_ide_metadata_workspace_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "c" * 32
            self._write_workspace(
                home, wid, "/Users/me/Workspace/Project/project-alpha/.cursor/agents"
            )
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 10:05:00 [info] indexing skills "
                        "workspaceStorage/" + wid
                    )
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_exact_copilot_metadata_leaf(self):
        # Align with vscode_fork: trailing ``/.copilot`` is IDE metadata.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "d" * 32
            self._write_workspace(
                home, wid, "/Users/me/Workspace/Project/project-alpha/.copilot"
            )
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 10:06:00 [info] indexing skills "
                        "workspaceStorage/" + wid
                    )
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_keeps_prefixed_vscode_workspace_leaf(self):
        # ``/.vscode`` must not swallow ``/.vscode-community``.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "e" * 32
            self._write_workspace(
                home, wid, "/Users/me/Workspace/Project/.vscode-community"
            )
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 10:07:00 [info] focus "
                        "workspaceStorage/" + wid
                    )
                ],
            )
            out = self._collect(home)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["anchors"]["dir"], ".vscode-community")

    def test_skips_github_agents_metadata_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            # Line noise alone would not drop a path-only event; path guard must.
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:10:00 [info] discovered "
                    "/Users/me/Workspace/Project/project-alpha/.github/agents/helper.md"
                ],
            )
            # Bypass [local]/noise by using a non-matching prefix — path guard only.
            self.assertEqual(self._collect(home), [])


class CursorScrapedPathVouchTests(unittest.TestCase):
    """GH-529: a path in a log line is only a workspace if an opened one vouches."""

    _write_workspace = CursorPathGuardTests._write_workspace
    _write_log = CursorPathGuardTests._write_log
    _collect = CursorPathGuardTests._collect

    def test_unvouched_path_produces_no_event(self):
        # The reported symptom: a directory some harness writes session data into
        # is mentioned on many log lines and outranks every real repository.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:00:00 [info] wrote "
                    "/Users/me/scratch/harness-sessions/run-91/state.json",
                    "2026-04-22 10:00:01 [info] wrote "
                    "/Users/me/scratch/harness-sessions/run-92/state.json",
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_path_inside_an_opened_workspace_attributes_to_its_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_workspace(home, "a" * 32, "/Users/me/Workspace/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:02:00 [info] saved "
                    "/Users/me/Workspace/project-alpha/src/deep/module.ts"
                ],
            )
            out = self._collect(home)
            self.assertEqual(len(out), 1)
            # The root, not "deep" — a nested file belongs to the project.
            self.assertEqual(out[0]["anchors"]["dir"], "project-alpha")

    def test_nested_workspace_wins_over_its_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_workspace(home, "a" * 32, "/Users/me/Workspace/outer")
            self._write_workspace(home, "b" * 32, "/Users/me/Workspace/outer/inner")
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:03:00 [info] saved "
                    "/Users/me/Workspace/outer/inner/src/app.ts"
                ],
            )
            out = self._collect(home)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["anchors"]["dir"], "inner")

    def test_metadata_path_inside_an_opened_workspace_is_still_skipped(self):
        # Regression: resolving to the workspace root before the metadata guards
        # ran made `<project>/.cursor/...` look like ordinary work in the root.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_workspace(home, "a" * 32, "/Users/me/Workspace/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:05:00 [info] wrote "
                    "/Users/me/Workspace/project-alpha/.cursor/state.json"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_multi_root_workspace_folders_are_vouched(self):
        # A .code-workspace entry names the config file, not the folders in it;
        # without expanding it every multi-root folder fails containment.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / "Workspace" / "team.code-workspace"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            # Absolute folder entry: the collector's path extractor only matches
            # /Users/... paths, which a temp dir can never be.
            cfg.write_text(
                json.dumps(
                    {"folders": [{"path": "/Users/me/Workspace/project-alpha"}]}
                ),
                encoding="utf-8",
            )
            self._write_workspace(home, "a" * 32, str(cfg))
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:07:00 [info] saved "
                    "/Users/me/Workspace/project-alpha/src/app.ts"
                ],
            )
            out = self._collect(home)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["anchors"]["dir"], "project-alpha")

    def test_sibling_of_an_opened_workspace_is_not_vouched(self):
        # Prefix matching must respect path boundaries: "project-alpha-scratch"
        # is not inside "project-alpha".
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_workspace(home, "a" * 32, "/Users/me/Workspace/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    "2026-04-22 10:04:00 [info] wrote "
                    "/Users/me/Workspace/project-alpha-scratch/tmp.json"
                ],
            )
            self.assertEqual(self._collect(home), [])


if __name__ == "__main__":
    unittest.main()
