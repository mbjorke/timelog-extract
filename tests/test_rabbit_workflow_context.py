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


if __name__ == "__main__":
    unittest.main()
