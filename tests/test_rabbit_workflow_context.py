"""Tests for scripts/rabbit_workflow_context.sh JSON contract."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rabbit_workflow_context.sh"


class RabbitWorkflowContextTests(unittest.TestCase):
    def test_emits_required_json_keys(self):
        if not SCRIPT.is_file():
            self.skipTest("rabbit_workflow_context.sh missing")
        proc = subprocess.run(
            [str(SCRIPT), "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        data = json.loads(proc.stdout)
        for key in (
            "branch",
            "head",
            "workflow_mode",
            "local_task_lanes",
            "blockers",
            "warnings",
            "questions",
        ):
            self.assertIn(key, data)
        if data.get("workflow_mode") == "gitbutler":
            self.assertIn("gitbutler_sync", data)
            sync = data["gitbutler_sync"]
            for sync_key in ("common_base", "main_behind", "dead_lanes", "pull_check_ok"):
                self.assertIn(sync_key, sync)
        self.assertIsInstance(data["questions"], list)
        self.assertGreaterEqual(len(data["questions"]), 1)
        if str(data.get("branch", "")).startswith("task/"):
            self.assertGreaterEqual(
                len(data.get("local_task_lanes", [])),
                1,
                msg="task/* lane discovery should list at least the current branch",
            )
        worktrees = data.get("worktrees", [])
        if len(worktrees) > 1:
            self.assertEqual(
                len(worktrees),
                len({w for w in worktrees if w}),
                msg="each worktree path should be its own JSON entry",
            )

    def test_chat_summary_markdown(self):
        if not SCRIPT.is_file():
            self.skipTest("rabbit_workflow_context.sh missing")
        proc = subprocess.run(
            [str(SCRIPT), "--chat-summary"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(proc.returncode, (0, 1, 2), msg=proc.stderr or proc.stdout)
        out = proc.stdout
        self.assertIn("## Kanin-loop workflow preflight", out)
        self.assertIn("### Questions", out)
        self.assertIn("scripts/rabbit_workflow_context.sh --ack", out)
        self.assertIn("### Local task/* lanes", out)


if __name__ == "__main__":
    unittest.main()
