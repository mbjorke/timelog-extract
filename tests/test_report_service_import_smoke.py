"""Fresh-process import smoke: catches circular imports between cli and report_service."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class ReportServiceImportSmokeTests(unittest.TestCase):
    def test_import_run_timelog_report_in_clean_subprocess(self):
        """Golden eval and other tools import report_service first; CLI registration must not deadlock."""
        code = (
            "from core.report_service import run_timelog_report; "
            "assert callable(run_timelog_report)"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
