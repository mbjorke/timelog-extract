"""Tests for core.report_historical_totals."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core.cli_options import TimelogRunOptions


class ReportHistoricalTotalsTests(unittest.TestCase):
    def test_history_uses_all_time_git(self):
        from core.report_historical_totals import compute_report_historical_totals

        args = TimelogRunOptions(history_source=True)
        dt = datetime(2026, 6, 1, tzinfo=timezone.utc)
        with patch(
            "core.report_historical_totals.compute_git_project_totals",
            return_value={"p": 1.0},
        ) as mock_git:
            with patch(
                "core.report_historical_totals.compute_timelog_project_totals",
                return_value={"p": 2.0},
            ):
                wl, git, enabled = compute_report_historical_totals(
                    args=args,
                    profiles=[],
                    worklog_paths=["/tmp/TIMELOG.md"],
                    local_tz=timezone.utc,
                    dt_from=dt,
                    dt_to=dt,
                    classify_project_fn=lambda t, p: "p",
                    make_event_fn=lambda *a, **k: {},
                    worklog_source="TIMELOG.md",
                    ai_sources=set(),
                )

        self.assertTrue(enabled)
        self.assertEqual(git, {"p": 1.0})
        self.assertEqual(wl, {"p": 2.0})
        self.assertNotIn("dt_from", mock_git.call_args.kwargs)

    def test_legacy_git_uses_period_bounds(self):
        from core.report_historical_totals import compute_report_historical_totals

        args = TimelogRunOptions(git_source=True, history_source=False)
        dt_from = datetime(2026, 6, 1, tzinfo=timezone.utc)
        dt_to = datetime(2026, 6, 7, tzinfo=timezone.utc)
        with patch(
            "core.report_historical_totals.compute_git_project_totals",
            return_value={},
        ) as mock_git:
            wl, git, enabled = compute_report_historical_totals(
                args=args,
                profiles=[],
                worklog_paths=[],
                local_tz=timezone.utc,
                dt_from=dt_from,
                dt_to=dt_to,
                classify_project_fn=lambda t, p: "p",
                make_event_fn=lambda *a, **k: {},
                worklog_source="TIMELOG.md",
                ai_sources=set(),
            )

        self.assertTrue(enabled)
        self.assertEqual(wl, {})
        self.assertEqual(mock_git.call_args.kwargs["dt_from"], dt_from)
        self.assertEqual(mock_git.call_args.kwargs["dt_to"], dt_to)

    def test_history_table_cells_distinguishes_zero_from_missing(self):
        from core.cli_status_history import history_table_cells

        cells = history_table_cells(
            "project-alpha",
            show_history=True,
            git_totals={"project-alpha": 0.0},
            timelog_totals={},
        )
        self.assertEqual(cells, ["0.0h", "—"])


if __name__ == "__main__":
    unittest.main()
