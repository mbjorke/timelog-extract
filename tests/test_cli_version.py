"""CLI --version flag."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


SEMVER = re.compile(r"^\d+\.\d+\.\d+(rc\d+)?(-dev)?$")


class CliVersionTests(unittest.TestCase):
    """Smoke test version output from the entry script."""

    def _version_line(self, flag: str) -> str:
        script = ROOT / "timelog_extract.py"
        completed = subprocess.run(
            [sys.executable, str(script), flag],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(completed.stderr, "")
        return completed.stdout.strip()

    def test_version_flag_prints_name_and_semver(self):
        line = self._version_line("--version")
        self.assertTrue(line.startswith("timelog-extract "))
        self.assertRegex(line.removeprefix("timelog-extract ").strip(), SEMVER)

    def test_short_flags_agree_in_both_cases(self):
        # GH-525: the installer's remediation text says `gittan -V`, but lowercase
        # is what most people type, and it used to dead-end with "No such option"
        # at the moment someone is checking whether an upgrade landed.
        upper = self._version_line("-V")
        lower = self._version_line("-v")
        self.assertEqual(upper, lower)
        self.assertEqual(upper, self._version_line("--version"))


if __name__ == "__main__":
    unittest.main()
