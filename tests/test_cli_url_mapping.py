"""Regression tests for `gittan review` interactive-mapping robustness (#424).

F8: the interactive path must not crash with a raw traceback when stdin is not
a terminal — it should print a friendly message and exit non-zero.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import typer

from core.cli_triage_map_candidates import UrlCandidate

ENTRY = Path(__file__).resolve().parent.parent / "timelog_extract.py"


def _fake_row():
    return UrlCandidate(
        title="Example",
        url_key="customer-a.test",
        suggested_project="Uncategorized",
        confidence_label="low",
        confidence_score=0.0,
        impact_hours=0.0,
        events=3,
        days=1,
        last_seen="2026-07-21",
        sample_urls=["https://customer-a.test/"],
    )


class NonTtyGuardTests(unittest.TestCase):
    def test_interactive_review_on_non_tty_exits_before_heavy_work(self):
        from core import cli_url_mapping

        # The candidate load runs a report; a non-TTY interactive run must bail
        # before it (performance) and never reach the load or a prompt.
        def _must_not_run(*_a, **_k):
            raise AssertionError("candidate load / prompt must not run without a TTY")

        out = io.StringIO()
        with mock.patch.object(cli_url_mapping, "should_prompt", return_value=False), \
             mock.patch.object(cli_url_mapping, "load_triage_map_candidates", _must_not_run), \
             mock.patch.object(cli_url_mapping.questionary, "select", _must_not_run):
            with redirect_stdout(out):
                with self.assertRaises(typer.Exit) as ctx:
                    cli_url_mapping.run_url_mapping_review(last_week=True, json_out=False)

        self.assertEqual(ctx.exception.exit_code, 1)
        self.assertIn("interactive terminal", out.getvalue())

    def test_json_path_does_not_require_a_tty(self):
        from core import cli_url_mapping

        out = io.StringIO()
        # Even with no interactive terminal, --json must produce a plan.
        with mock.patch.object(cli_url_mapping, "should_prompt", return_value=False), \
             mock.patch.object(cli_url_mapping, "load_triage_map_candidates", return_value=[_fake_row()]):
            with redirect_stdout(out):
                with self.assertRaises(typer.Exit) as ctx:
                    cli_url_mapping.run_url_mapping_review(last_week=True, json_out=True)

        self.assertEqual(ctx.exception.exit_code, 0)
        # --json must emit parseable JSON even without a TTY, and stdout must
        # start with the JSON (F5: no leading diagnostics on stdout).
        import json

        raw = out.getvalue()
        self.assertTrue(raw.lstrip().startswith("{"), f"stdout not pure JSON: {raw[:60]!r}")
        json.loads(raw)


class ReviewJsonCliContractTests(unittest.TestCase):
    """End-to-end: the real `gittan review --json` command, not mocked internals."""

    def test_review_json_stdout_is_pure_json_warnings_on_stderr(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "timelog_projects.json").write_text(
                json.dumps({"projects": [{"name": "alpha", "match_terms": ["alpha"]}]}),
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["GITTAN_HOME"] = str(home)
            completed = subprocess.run(
                [sys.executable, str(ENTRY), "review", "--json", "--last-week"],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
        # stdout is a single JSON object; any collector warnings stay on stderr.
        payload = json.loads(completed.stdout)
        self.assertEqual(payload.get("command"), "gittan review")


if __name__ == "__main__":
    unittest.main()
