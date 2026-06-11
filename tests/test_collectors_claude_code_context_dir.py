"""Claude Code CLI collector preserves a privacy-safe working-directory leaf.

See docs/specs/working-directory-anchor-signal.md.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.ai_logs import _cwd_leaf, collect_claude_code


def _make_event(source, ts, detail, project, context_dir=None):
    event = {"source": source, "timestamp": ts, "detail": detail, "project": project}
    if context_dir:
        event["context_dir"] = context_dir
    return event


def _classify(_text, _profiles):
    return "Uncategorized"


class ClaudeCodeContextDirTests(unittest.TestCase):
    def _write_session(self, home: Path, dir_name: str, cwd: str) -> None:
        proj_dir = home / ".claude" / "projects" / dir_name
        proj_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": "2026-06-11T09:00:00Z",
            "cwd": cwd,
            "message": {"content": "log"},
            "type": "user",
        }
        (proj_dir / "session.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")

    def test_context_dir_is_cwd_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_session(
                home, "-home-user-timelog-extract", "/home/user/timelog-extract"
            )
            events = collect_claude_code(
                profiles=[],
                dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 30, tzinfo=timezone.utc),
                home=home,
                classify_project=_classify,
                make_event=_make_event,
            )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["context_dir"], "timelog-extract")
            # detail is untouched and carries no path/home/username segment
            self.assertEqual(events[0]["detail"], "log")
            self.assertNotIn("/", events[0]["context_dir"])

    def test_cwd_leaf_helper(self) -> None:
        self.assertEqual(_cwd_leaf({"cwd": "/Users/someone/Workspace/repo-x/"}), "repo-x")
        self.assertEqual(_cwd_leaf({"cwd": "/home/user/timelog-extract"}), "timelog-extract")
        self.assertIsNone(_cwd_leaf({"cwd": ""}))
        self.assertIsNone(_cwd_leaf({}))
        self.assertIsNone(_cwd_leaf("not-a-dict"))


if __name__ == "__main__":
    unittest.main()
