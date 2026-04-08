"""CLI --version flag."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CliVersionTests(unittest.TestCase):
    """Smoke test version output from the entry script."""

    def test_version_flag_prints_name_and_semver(self):
        script = ROOT / "timelog_extract.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--version"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(completed.stderr, "")
        line = completed.stdout.strip()
        self.assertTrue(line.startswith("timelog-extract "))
        rest = line.removeprefix("timelog-extract ").strip()
        self.assertRegex(rest, re.compile(r"^\d+\.\d+\.\d+(-dev)?$"))


if __name__ == "__main__":
    unittest.main()
