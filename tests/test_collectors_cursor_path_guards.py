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


if __name__ == "__main__":
    unittest.main()
