"""Regression tests for `gittan review` interactive-mapping robustness (#424).

F8: the interactive path must not crash with a raw traceback when stdin is not
a terminal — it should print a friendly message and exit non-zero.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

import typer

from core.cli_triage_map_candidates import UrlCandidate


def _fake_row():
    return UrlCandidate(
        title="Example",
        url_key="example.lovableproject.com",
        suggested_project="Uncategorized",
        confidence_label="low",
        confidence_score=0.0,
        impact_hours=0.0,
        events=3,
        days=1,
        last_seen="2026-07-21",
        sample_urls=["https://example.lovableproject.com/"],
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


if __name__ == "__main__":
    unittest.main()
