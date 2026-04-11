"""Regression smoke tests from CLI development (Typer, gittan, Rich, questionary).

These catch failures that showed up when running the installed console script from
arbitrary directories, or when edits broke core/cli.py syntax.
"""

import ast
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "timelog_extract.py"


class CliRegressionSmokeTests(unittest.TestCase):
    """Minimal subprocess/import checks."""

    def test_timelog_extract_imports_when_loaded_by_path(self):
        """Console scripts resolve timelog_extract as a file; repo packages must still load."""
        spec = importlib.util.spec_from_file_location("_te_entry", ENTRY)
        self.assertIsNotNone(spec and spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # noqa: SLF001 — stdlib pattern
        self.assertTrue(hasattr(mod, "main"))

    def test_doctor_runs_from_foreign_cwd(self):
        """Regression: ModuleNotFoundError: outputs when cwd != repo (gittan from PATH)."""
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [sys.executable, str(ENTRY), "doctor"],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=120,
            )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stderr or completed.stdout,
        )
        self.assertIn("Gittan Health Check", completed.stdout)

    def test_core_cli_py_compiles(self):
        """Regression: bad search/replace left invalid syntax (e.g. truncated for-loop)."""
        path = ROOT / "core" / "cli.py"
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
