"""Cancellation contract for the interactive review loops.

Three states must stay distinguishable at every prompt: the user interrupted
(questionary returns None), the user deliberately declined (False, or an empty
string they typed), or the input failed validation. Collapsing any pair of them
is how a quit turned into "carry on" and a decline turned into exit 130.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import typer
from rich.console import Console

from core.uncategorized_review import print_review_cancelled


class ReviewCancelledMessageTests(unittest.TestCase):
    """The message must match what is already persisted."""

    def _render(self, *, applied_any: bool) -> str:
        console = Console(record=True, width=100, force_terminal=False)
        print_review_cancelled(console, applied_any=applied_any)
        return " ".join(console.export_text().split())

    def test_reports_no_writes_when_nothing_was_applied(self):
        self.assertIn("Cancelled before writing config.", self._render(applied_any=False))

    def test_reports_prior_writes_once_a_cluster_was_applied(self):
        text = self._render(applied_any=True)
        self.assertNotIn(
            "before writing config",
            text,
            "each accepted cluster is saved immediately, so this claim would be false",
        )
        self.assertIn("remain in your config", text)


class AbSuggestionsCancellationTests(unittest.TestCase):
    """`.ask() or ""` turned Ctrl+C into an empty project name and continued."""

    def _run(self, ask_value):
        from core.cli_review_uncategorized import run_uncategorized_cluster_review

        cluster = MagicMock()
        cluster.source = "Chrome"
        cluster.count = 3
        cluster.samples = ["sample"]
        cluster.rule_type = "match_terms"
        cluster.rule_value = "alpha"

        report = MagicMock()
        report.included_events = [{"project": "Uncategorized", "detail": "alpha"}]

        mod = "core.cli_review_uncategorized"
        with patch(f"{mod}.warn_deprecated_command"), \
             patch(f"{mod}._apply_timeframe_prompt", side_effect=lambda *a: a), \
             patch("core.report_service.run_timelog_report", return_value=report), \
             patch(f"{mod}.count_uncategorized_noise_events", return_value=0), \
             patch(f"{mod}.build_uncategorized_clusters", return_value=[cluster]), \
             patch(f"{mod}._load_projects_payload", return_value={"projects": []}), \
             patch(f"{mod}.gather_ab_suggestions") as gather, \
             patch(f"{mod}.questionary") as q:
            q.text.return_value.ask.return_value = ask_value
            q.select.return_value.ask.return_value = "Quit"
            try:
                run_uncategorized_cluster_review(
                    ab_suggestions=True,
                    projects_config="/nonexistent/timelog_projects.json",
                )
                return None, gather.called
            except typer.Exit as exc:
                return exc.exit_code, gather.called

    def test_ctrl_c_at_target_prompt_exits_130(self):
        code, gathered = self._run(None)
        self.assertEqual(code, 130)
        self.assertFalse(gathered, "must not proceed into suggestion gathering after a quit")

    def test_empty_answer_still_skips_rather_than_exiting(self):
        code, gathered = self._run("")
        self.assertIsNone(code, "an empty name is a skip, not an interrupt")
        self.assertFalse(gathered)


if __name__ == "__main__":
    unittest.main()
