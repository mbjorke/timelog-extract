"""Tests for scripts/rabbit_workflow_hygiene.sh fail-closed guards."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rabbit_workflow_hygiene.sh"


class RabbitWorkflowHygieneTests(unittest.TestCase):
    def test_help_exits_zero(self):
        if not SCRIPT.is_file():
            self.skipTest("rabbit_workflow_hygiene.sh missing")
        proc = subprocess.run(
            [str(SCRIPT), "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("dry-run", proc.stdout)

    def test_dry_run_with_empty_dead_lanes(self):
        if not SCRIPT.is_file():
            self.skipTest("rabbit_workflow_hygiene.sh missing")
        current = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if not current.startswith("gitbutler/"):
            self.skipTest("requires gitbutler/workspace")
        with tempfile.TemporaryDirectory() as tmp:
            preflight_path = Path(tmp) / "preflight.json"
            preflight = {
                "gitbutler_sync": {
                    "dead_lanes": [],
                    "main_behind": 0,
                    "pull_check_ok": True,
                }
            }
            preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
            proc = subprocess.run(
                [str(SCRIPT), "--dry-run", "--preflight", str(preflight_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertIn("but clean", proc.stdout)


if __name__ == "__main__":
    unittest.main()
