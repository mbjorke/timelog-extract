"""Claude Code CLI collector preserves a privacy-safe working-directory leaf.

See docs/specs/working-directory-anchor-signal.md.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.ai_logs import (
    _branch_leaf,
    _cwd_leaf,
    _meaningful_label,
    _meaningful_leaf,
    collect_claude_code,
)

from tests.event_helpers import make_test_event


def _classify(_text, _profiles):
    return "Uncategorized"


class ClaudeCodeContextDirTests(unittest.TestCase):
    def _write_session(self, home: Path, dir_name: str, cwd: str, branch: str | None = None) -> None:
        proj_dir = home / ".claude" / "projects" / dir_name
        proj_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": "2026-06-11T09:00:00Z",
            "cwd": cwd,
            "message": {"content": "fix export regression"},
            "type": "user",
        }
        if branch is not None:
            entry["gitBranch"] = branch
        (proj_dir / "session.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")

    def _collect(self, home: Path):
        return collect_claude_code(
            profiles=[],
            dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            dt_to=datetime(2026, 6, 30, tzinfo=timezone.utc),
            home=home,
            classify_project=_classify,
            make_event=make_test_event,
        )

    def test_context_dir_is_cwd_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_session(
                home, "-home-user-timelog-extract", "/home/user/timelog-extract"
            )
            events = self._collect(home)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["anchors"]["dir"], "timelog-extract")
            # detail is untouched and carries no path/home/username segment
            self.assertEqual(events[0]["detail"], "fix export regression")
            self.assertNotIn("/", events[0]["anchors"]["dir"])

    def test_branch_anchor_drops_namespace_and_keeps_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_session(
                home,
                "-home-user-timelog-extract",
                "/home/user/timelog-extract",
                branch="feature/project-beta-dashboard",
            )
            events = self._collect(home)
            self.assertEqual(len(events), 1)
            # The namespace segment (feature/) is dropped; the project leaf stays.
            self.assertEqual(events[0]["anchors"]["branch"], "project-beta-dashboard")
            self.assertEqual(events[0]["anchors"]["dir"], "timelog-extract")

    def test_generic_branch_yields_no_branch_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_session(
                home, "-home-user-timelog-extract", "/home/user/timelog-extract", branch="main"
            )
            events = self._collect(home)
            self.assertEqual(len(events), 1)
            self.assertNotIn("branch", events[0]["anchors"])

    def test_branch_leaf_helper(self) -> None:
        self.assertEqual(_branch_leaf({"gitBranch": "claude/project-beta-CeFO5"}), "project-beta-cefo5")
        self.assertEqual(_branch_leaf({"gitBranch": "project-alpha"}), "project-alpha")
        self.assertIsNone(_branch_leaf({"gitBranch": "main"}))
        self.assertIsNone(_branch_leaf({"gitBranch": ""}))
        self.assertIsNone(_branch_leaf({}))

    def test_meaningful_label_helper(self) -> None:
        self.assertEqual(_meaningful_label("Project Beta home redesign"), "Project Beta home redesign")
        self.assertIsNone(_meaningful_label("session"))
        self.assertIsNone(_meaningful_label("Session"))
        self.assertIsNone(_meaningful_label(""))
        self.assertIsNone(_meaningful_label(None))

    def test_cwd_leaf_helper(self) -> None:
        self.assertEqual(_cwd_leaf({"cwd": "/Users/someone/Workspace/repo-x/"}), "repo-x")
        self.assertEqual(_cwd_leaf({"cwd": "/home/user/timelog-extract"}), "timelog-extract")
        self.assertIsNone(_cwd_leaf({"cwd": ""}))
        self.assertIsNone(_cwd_leaf({}))
        self.assertIsNone(_cwd_leaf("not-a-dict"))

    def test_meaningful_leaf_rejects_hash_like_names(self) -> None:
        # Real project leaf passes (even with a hyphen).
        self.assertEqual(_meaningful_leaf("timelog-extract"), "timelog-extract")
        self.assertEqual(_meaningful_leaf("project-beta"), "project-beta")
        # Hash-like tmp dir names are rejected as noise.
        self.assertIsNone(_meaningful_leaf("a1b2c3d4e5f60718293a4b5c6d7e8f90"))
        self.assertIsNone(_meaningful_leaf(""))
        self.assertIsNone(_meaningful_leaf(None))

    def test_session_title_propagates_label_from_desktop_metadata(self) -> None:
        cli_id = "ae47de83-d335-4f7d-9252-3a817f7d91b9"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            proj_dir = home / ".claude" / "projects" / "-Users-someone-timelog-extract"
            proj_dir.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": "2026-06-11T09:00:00Z",
                "message": {"content": "merge onboarding verify PR"},
                "type": "user",
            }
            (proj_dir / f"{cli_id}.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
            meta_dir = (
                home
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude-code-sessions"
                / "parent"
                / "child"
            )
            meta_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "sessionId": "local_4244714f-74a8-4623-a118-59b9b7f81b28",
                "cliSessionId": cli_id,
                "title": "Toggle integration progress",
                "cwd": "/home/user/timelog-extract",
            }
            (meta_dir / "local_4244714f.json").write_text(json.dumps(meta), encoding="utf-8")

            def classify(text, profiles):
                if "timelog-extract" in text or "toggle" in text.lower():
                    return "timelog-extract"
                return "Uncategorized"

            events = collect_claude_code(
                profiles=[],
                dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 30, tzinfo=timezone.utc),
                home=home,
                classify_project=classify,
                make_event=make_test_event,
            )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["anchors"]["label"], "Toggle integration progress")
            self.assertEqual(events[0]["project"], "timelog-extract")
            self.assertEqual(events[0]["detail"], "merge onboarding verify PR")

    def test_skips_pr_link_and_bare_log_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            proj_dir = home / ".claude" / "projects" / "-Users-mbjorke-timelog-extract"
            proj_dir.mkdir(parents=True, exist_ok=True)
            lines = [
                {
                    "timestamp": "2026-06-11T13:13:00Z",
                    "cwd": "/Users/someone/timelog-extract",
                    "type": "pr-link",
                    "message": {"content": "log"},
                },
                {
                    "timestamp": "2026-06-11T13:14:00Z",
                    "cwd": "/Users/someone/timelog-extract",
                    "type": "user",
                    "message": {"content": "log"},
                },
                {
                    "timestamp": "2026-06-11T13:15:00Z",
                    "cwd": "/Users/someone/timelog-extract",
                    "type": "user",
                    "message": {"content": "review billing export"},
                },
            ]
            (proj_dir / "session.jsonl").write_text(
                "\n".join(json.dumps(row) for row in lines) + "\n",
                encoding="utf-8",
            )
            events = self._collect(home)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["detail"], "review billing export")


if __name__ == "__main__":
    unittest.main()
