"""GH-537: the lifetime column has to survive the whole call chain, not just the sum.

The aggregation was unit-tested and green while `gittan report` would have raised
`TypeError` on every non-empty run, because `_print_report` sits between the CLI
and the renderer and did not accept the new argument. Nothing exercised that seam,
so these tests do.
"""

from __future__ import annotations

import argparse
import inspect
import io
import unittest

from rich.console import Console

from core.report_service import _print_report
from outputs.terminal_report_sections import print_project_hour_review_section


def _args() -> argparse.Namespace:
    """The attributes the report sections actually read."""
    return argparse.Namespace(
        additive_summary=False,
        billable_unit=0.0,
        min_session=15,
        min_session_passive=5,
        compact=False,
        source_summary=False,
        screen_time="off",
    )


class LifetimeColumnWiringTests(unittest.TestCase):
    def test_print_report_accepts_what_the_cli_actually_passes(self):
        # Mirrors the keyword set core/report_cli.py sends. A missing parameter
        # anywhere in the chain is a crash on the real report path, not a
        # rendering nicety.
        _print_report(
            {},
            {},
            None,
            [],
            _args(),
            None,
            None,
            None,
            None,
            lifetime_window=("2026-05-04", "2026-06-10"),
            presence_edge_gaps=None,
            presence_bracketing=None,
            billable_raw_by_project=None,
            reported_billing=False,
        )

    def test_the_window_reaches_the_renderer(self):
        forwarded = inspect.signature(_print_report).parameters
        self.assertIn("lifetime_window", forwarded)
        section = inspect.signature(print_project_hour_review_section).parameters
        self.assertIn("lifetime_window", section)

    def _render(self, *, totals, window):
        console = Console(file=io.StringIO(), width=200, no_color=True)
        print_project_hour_review_section(
            console,
            args=_args(),
            overall_days={},
            # {project: {day: payload}} — the shape the renderer sums over.
            project_reports={"project-alpha": {"2026-06-10": {"hours": 1.0, "sessions": []}}},
            profiles=[{"name": "project-alpha", "customer": "Customer A"}],
            timelog_project_totals=totals,
            git_project_totals=None,
            session_duration_hours_fn=lambda *a, **k: 0.0,
            billable_total_hours_fn=lambda *a, **k: 0.0,
            lifetime_window=window,
        )
        return console.file.getvalue()

    def test_header_names_the_window_it_covers(self):
        # The withdrawn column's failure was its label, not its number: it implied
        # a comparison it could not support. This one must say what it covers, and
        # must never imply all-time over a store that prunes.
        out = self._render(
            totals={"project-alpha": 4.75}, window=("2026-05-04", "2026-06-10")
        )
        self.assertIn("Lifetime", out)
        self.assertIn("2026-05-04", out)
        self.assertIn("2026-06-10", out)
        self.assertNotIn("Total observed", out)

    def test_no_column_when_there_is_nothing_to_show(self):
        out = self._render(totals=None, window=None)
        self.assertNotIn("Lifetime", out)


if __name__ == "__main__":
    unittest.main()
