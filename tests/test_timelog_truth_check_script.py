from __future__ import annotations

import datetime as dt
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "timelog_truth_check.sh"


class TimelogTruthCheckScriptTests(unittest.TestCase):
    def test_help_shows_required_artifacts(self):
        completed = subprocess.run(
            ["bash", str(SCRIPT), "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
        self.assertIn("benchmark_manifest.json", completed.stdout)
        self.assertIn("benchmark_metrics.json", completed.stdout)
        self.assertIn("determinism_replay_report.json", completed.stdout)

    def test_blocks_open_window_without_allow_flag(self):
        today = dt.date.today().isoformat()
        completed = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--from",
                "2026-01-01",
                "--to",
                today,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Use a closed window or pass --allow-open-window", completed.stderr)

    def test_closed_window_generates_required_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "truth-check-out"
            completed = subprocess.run(
                [
                    "bash",
                    str(SCRIPT),
                    "--from",
                    "2026-01-01",
                    "--to",
                    "2026-01-31",
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
            self.assertTrue((out_dir / "benchmark_manifest.json").exists())
            self.assertTrue((out_dir / "benchmark_metrics.json").exists())
            self.assertTrue((out_dir / "determinism_replay_report.json").exists())
            self.assertTrue((out_dir / "README.md").exists())


if __name__ == "__main__":
    unittest.main()
