"""Golden eval is run via scripts/run_golden_eval.py (subprocess for clean TZ/path)."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class GoldenEvalScriptTests(unittest.TestCase):
    def test_golden_eval_check_exits_zero(self):
        try:
            r = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "run_golden_eval.py"), "--check"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"Golden eval timed out: {exc}")
        self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
