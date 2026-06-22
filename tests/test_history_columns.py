"""Tests for --history historical columns (Git all-time + TIMELOG all-time)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core.cli_options import TimelogRunOptions


class HistoryColumnsReportTests(unittest.TestCase):
    def test_history_populates_git_all_time_and_timelog_totals(self):
        from core.report_service import run_timelog_report

        fake_git = {"project-alpha": 12.5}
        fake_timelog = {"project-alpha": 3.0}
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
                    return_value=(fake_timelog, fake_git, True),
                ) as mock_hist:
                        report = run_timelog_report(
                            options.projects_config,
                            options.date_from,
                            options.date_to,
                            options,
                        )

        self.assertEqual(report.git_project_totals, fake_git)
        self.assertEqual(report.timelog_project_totals, fake_timelog)
        mock_hist.assert_called_once()

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

    def test_history_skips_timelog_when_no_worklog_paths(self):
        from core.report_service import run_timelog_report

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
            with patch("core.report_service.aggregate_report") as mock_agg:
                from core.report_aggregate import AggregationResult

                mock_agg.return_value = AggregationResult(
                    all_events=[],
                    included_events=[],
                    grouped={},
                    overall_days={},
                    project_reports={},
                )
                with patch("core.report_service.build_run_context") as mock_ctx:
                    from types import SimpleNamespace

                    mock_ctx.return_value = SimpleNamespace(
                        args=options,
                        dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
                        dt_to=datetime(2026, 6, 1, 23, 59, 59, tzinfo=timezone.utc),
                        profiles=[],
                        loaded_config_path=None,
                        worklog_path=None,
                        worklog_paths=[],
                        source_strategy_effective="balanced",
                    )
                    with patch(
                        "core.report_service.compute_report_historical_totals",
                        return_value=({}, {}, True),
                    ) as mock_hist:
                            report = run_timelog_report(
                                options.projects_config,
                                options.date_from,
                                options.date_to,
                                options,
                            )

        mock_hist.assert_called_once()
        self.assertEqual(report.timelog_project_totals, {})


if __name__ == "__main__":
    unittest.main()
