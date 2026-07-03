"""Tests for scripts/rabbit_workflow_context_chat.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.rabbit_workflow_context_chat import render_chat_summary

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rabbit_workflow_context_chat.py"


class RabbitWorkflowContextChatTests(unittest.TestCase):
    def test_render_minimal_payload(self):
        md = render_chat_summary(
            {
                "branch": "task/example",
                "head": "abc123456789",
                "workflow_mode": "plain_git",
                "dirty": False,
                "blockers": [],
                "warnings": [],
                "questions": [{"id": "mode", "prompt": "Mode?", "options": ["yes"]}],
                "local_task_lanes": [],
                "open_prs": [],
                "worktrees": [],
            }
        )
        self.assertIn("task/example", md)
        self.assertIn("### Questions", md)

    def test_cli_reads_json_file(self):
        if not SCRIPT.is_file():
            self.skipTest("chat renderer missing")
        payload = {
            "branch": "task/cli",
            "head": "deadbeef",
            "workflow_mode": "plain_git",
            "dirty": False,
            "blockers": [],
            "warnings": [],
            "questions": [],
            "local_task_lanes": [],
            "open_prs": [],
            "worktrees": [],
            "ack_command": "scripts/rabbit_workflow_context.sh --ack",
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=True
        ) as tmp:
            tmp.write(json.dumps(payload))
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), tmp.name],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("task/cli", proc.stdout)

    def test_render_tolerates_partial_entries(self):
        md = render_chat_summary(
            {
                "branch": "task/x",
                "head": "abc",
                "workflow_mode": "plain_git",
                "blockers": [{"detail": "no kind key"}],
                "warnings": [],
                "questions": [{"options": ["only option"]}],
                "open_prs": [{"title": "orphan title"}],
            }
        )
        self.assertIn("?", md)
        self.assertIn("orphan title", md)


if __name__ == "__main__":
    unittest.main()
