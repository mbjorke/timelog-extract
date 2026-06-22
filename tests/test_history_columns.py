"""Tests for --history columns (Total observed + Git estimate)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core.cli_options import TimelogRunOptions


class HistoryColumnsReportTests(unittest.TestCase):
    def test_history_populates_git_estimate_not_timelog(self):
        from core.report_service import run_timelog_report

        fake_git = {"project-alpha": 12.5}
        options = TimelogRunOptions(
            date_from="2026-06-01",
            date_to="2026-06-01",
            quiet=True,
            screen_time="off",
            chrome_source="off",
            mail_source="off",
            github_source="off",
            calendar_source="off",
            history_source=True,
            projects_config="tests/fixtures/golden_timelog_projects.json",
        )

        with patch("core.report_service.collect_runtime_events", return_value=([], {})):
            with patch(
                "core.report_service.aggregate_report",
            ) as mock_agg:
                from core.report_aggregate import AggregationResult

                mock_agg.return_value = AggregationResult(
                    all_events=[],
                    included_events=[],
                    grouped={},
                    overall_days={},
                    project_reports={},
                )
                with patch(
                    "core.report_service.compute_report_historical_totals",
                    return_value=({}, fake_git, True),
                ) as mock_hist:
                    with patch(
                        "core.report_service.compute_observed_all_time_totals",
                        return_value={"project-alpha": 99.0},
                    ) as mock_obs:
                        report = run_timelog_report(
                            options.projects_config,
                            options.date_from,
                            options.date_to,
                            options,
                        )

                self.assertEqual(report.git_project_totals, fake_git)
                self.assertEqual(report.observed_project_totals, {"project-alpha": 99.0})
                self.assertEqual(report.timelog_project_totals, {})
                mock_hist.assert_called_once()
                mock_obs.assert_called_once()

    def test_git_without_history_uses_period_bounds(self):
        from core.report_service import run_timelog_report

        options = TimelogRunOptions(
            date_from="2026-06-01",
            date_to="2026-06-07",
            quiet=True,
            screen_time="off",
            chrome_source="off",
            mail_source="off",
            github_source="off",
            calendar_source="off",
            git_source=True,
            history_source=False,
            projects_config="tests/fixtures/golden_timelog_projects.json",
        )

        with patch("core.report_service.collect_runtime_events", return_value=([], {})):
            with patch("core.report_service.aggregate_report") as mock_agg:
                from core.report_aggregate import AggregationResult

                mock_agg.return_value = AggregationResult(
                    all_events=[],
                    included_events=[],
                    grouped={},
                    overall_days={},
                    project_reports={},
                )
                with patch(
                    "core.report_service.compute_report_historical_totals",
                    return_value=({}, {"project-alpha": 1.0}, True),
                ) as mock_hist:
                    run_timelog_report(
                        options.projects_config,
                        options.date_from,
                        options.date_to,
                        options,
                    )

        mock_hist.assert_called_once()
        call_kw = mock_hist.call_args.kwargs
        self.assertEqual(call_kw["dt_from"].date().isoformat(), "2026-06-01")
        self.assertEqual(call_kw["dt_to"].date().isoformat(), "2026-06-07")


class AllAvailableWindowTests(unittest.TestCase):
    def test_resolve_all_available_window(self):
        from core.cli_date_range import resolve_all_available_window

        df, dt = resolve_all_available_window(now=datetime(2026, 6, 22).date())
        self.assertEqual(df, "2020-01-01")
        self.assertEqual(dt, "2026-06-22")

    def test_has_explicit_date_window(self):
        from core.cli_date_range import has_explicit_date_window

        self.assertTrue(has_explicit_date_window(date_from=None, date_to=None, today=True))
        self.assertFalse(has_explicit_date_window(date_from=None, date_to=None))


if __name__ == "__main__":
    unittest.main()
