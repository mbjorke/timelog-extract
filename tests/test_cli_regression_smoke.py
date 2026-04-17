"""Regression smoke tests from CLI development (Typer, gittan, Rich, questionary).

These catch failures that showed up when running the installed console script from
arbitrary directories, or when edits broke core/cli.py syntax.
"""

import ast
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "timelog_extract.py"


class CliRegressionSmokeTests(unittest.TestCase):
    """Minimal subprocess/import checks."""

    def _run_doctor(self, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [sys.executable, str(ENTRY), "doctor", *args],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stderr or completed.stdout,
        )
        self.assertIn("Gittan Health Check", completed.stdout)
        self.assertIn("CLI (gittan on PATH)", completed.stdout)
        return completed

    def test_timelog_extract_imports_when_loaded_by_path(self):
        """Console scripts resolve timelog_extract as a file; repo packages must still load."""
        spec = importlib.util.spec_from_file_location("_te_entry", ENTRY)
        self.assertIsNotNone(spec and spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # noqa: SLF001 — stdlib pattern
        self.assertTrue(hasattr(mod, "main"))

    def test_doctor_runs_from_foreign_cwd(self):
        """Regression: ModuleNotFoundError: outputs when cwd != repo (gittan from PATH)."""
        completed = self._run_doctor([])
        self.assertIn("Next steps", completed.stdout)
        self.assertIn("Toggl Source", completed.stdout)
        self.assertIn("Not configured (auto)", completed.stdout)

    def test_doctor_github_source_off_row_is_shown(self):
        completed = self._run_doctor(["--github-source", "off", "--github-user", "mbjorke"])
        self.assertIn("GitHub Source", completed.stdout)
        self.assertIn("Disabled (off)", completed.stdout)

    def test_doctor_github_source_auto_requires_user_when_missing(self):
        env = dict(os.environ)
        env.pop("GITHUB_USER", None)
        env.pop("GITHUB_TOKEN", None)
        completed = self._run_doctor(["--github-source", "auto"], env=env)
        self.assertIn("GitHub Source", completed.stdout)
        self.assertIn("Not configured (auto)", completed.stdout)

    def test_doctor_github_source_on_with_user_reports_token_state(self):
        env = dict(os.environ)
        env.pop("GITHUB_TOKEN", None)
        completed = self._run_doctor(["--github-source", "on", "--github-user", "mbjorke"], env=env)
        self.assertIn("GitHub Source", completed.stdout)
        self.assertIn("Enabled (on) for user 'mbjorke'", completed.stdout)
        self.assertIn("public API limits apply", completed.stdout)

    def test_doctor_rejects_invalid_github_source(self):
        completed = subprocess.run(
            [sys.executable, str(ENTRY), "doctor", "--github-source", "invalid"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Expected one of: auto, on, off", completed.stderr)

    def test_core_cli_py_compiles(self):
        """Regression: bad search/replace left invalid syntax (e.g. truncated for-loop)."""
        path = ROOT / "core" / "cli.py"
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_setup_global_timelog_dry_run(self):
        """New onboarding command should run without mutating machine state in dry-run mode."""
        completed = subprocess.run(
            [sys.executable, str(ENTRY), "setup-global-timelog", "--yes", "--dry-run"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stderr or completed.stdout,
        )
        self.assertIn("Dry run completed.", completed.stdout)
        self.assertIn("Gittan Global Timelog", completed.stdout)

    def test_setup_wizard_dry_run(self):
        """Full setup wizard should support non-interactive dry-run execution."""
        completed = subprocess.run(
            [sys.executable, str(ENTRY), "setup", "--yes", "--dry-run", "--skip-smoke"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stderr or completed.stdout,
        )
        self.assertIn("Next steps", completed.stdout)
        self.assertIn("Setup wizard completed.", completed.stdout)
        self.assertIn("GitHub env bootstrap", completed.stdout)
        self.assertIn("Gittan Setup", completed.stdout)

    def test_quick_start_cli_commands_finish_within_60_seconds_each(self):
        """Landing page quick start (after install): each CLI step should stay snappy on CI.

        Step 1 on gittan.sh is ``pip install`` / PyPI; that path is covered by the CI **package** job
        (wheel build + install). Here we time the three commands users run immediately after install:
        version check, non-interactive setup preview, and ``doctor`` from an empty directory.
        """
        budget_s = 60.0

        def run_timed(label: str, argv: list[str], cwd: str) -> subprocess.CompletedProcess:
            start = time.perf_counter()
            completed = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=int(budget_s),
            )
            elapsed = time.perf_counter() - start
            self.assertLess(
                elapsed,
                budget_s,
                msg=f"{label}: {' '.join(argv)} took {elapsed:.1f}s (limit {budget_s:g}s)",
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=completed.stderr or completed.stdout or label,
            )
            return completed

        run_timed("version", [sys.executable, str(ENTRY), "-V"], str(ROOT))
        run_timed(
            "setup_dry_run",
            [
                sys.executable,
                str(ENTRY),
                "setup",
                "--yes",
                "--dry-run",
                "--skip-smoke",
            ],
            str(ROOT),
        )
        with tempfile.TemporaryDirectory() as tmp:
            doc = run_timed("doctor", [sys.executable, str(ENTRY), "doctor"], tmp)
            self.assertIn("Next steps", doc.stdout)
            self.assertIn("Gittan Health Check", doc.stdout)

    def test_ux_heroes_command_prints_all_hero_titles(self):
        completed = subprocess.run(
            [sys.executable, str(ENTRY), "ux-heroes"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
        self.assertIn("Gittan Status", completed.stdout)
        self.assertIn("Gittan Doctor", completed.stdout)
        self.assertIn("Gittan Setup", completed.stdout)
        self.assertIn("Gittan Global Timelog", completed.stdout)
        self.assertIn("Gittan Report", completed.stdout)

    def test_jira_sync_help_includes_manual_confirmation(self):
        completed = subprocess.run(
            [sys.executable, str(ENTRY), "jira-sync", "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
        self.assertIn("Sync TIMELOG-derived hours to Jira worklogs", completed.stdout)
        self.assertIn("--require-confirm", completed.stdout)
        self.assertIn("--dry-run", completed.stdout)


if __name__ == "__main__":
    unittest.main()
