from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class _FakeReport:
    def __init__(self, project_reports, overall_days, included_events):
        self.project_reports = project_reports
        self.overall_days = overall_days
        self.included_events = included_events
        self.args = type("Args", (), {"min_session": 15, "min_session_passive": 5, "noise_profile": "strict"})()


class StatusIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_status_prints_overlap_note_when_project_rows_exceed_total(self):
        report = _FakeReport(
            project_reports={
                "A": {"2026-04-22": {"hours": 2.0, "sessions": [1, 2]}},
                "B": {"2026-04-22": {"hours": 2.0, "sessions": [3, 4]}},
            },
            overall_days={"2026-04-22": {"hours": 2.0, "sessions": [1, 2]}},
            included_events=[{"project": "A"}],
        )
        with patch("core.report_service.run_timelog_report", return_value=report):
            r = self.runner.invoke(app, ["status", "--yesterday"])
        self.assertEqual(r.exit_code, 0, msg=r.output)
        self.assertIn("project rows can overlap attribution", r.output)
        self.assertIn("Total is unique timeline time", r.output)

    def test_status_hides_overlap_note_when_rows_are_additive(self):
        report = _FakeReport(
            project_reports={
                "A": {"2026-04-22": {"hours": 1.0, "sessions": [1]}},
                "B": {"2026-04-22": {"hours": 1.0, "sessions": [2]}},
            },
            overall_days={"2026-04-22": {"hours": 2.0, "sessions": [1, 2]}},
            included_events=[{"project": "A"}],
        )
        with patch("core.report_service.run_timelog_report", return_value=report):
            r = self.runner.invoke(app, ["status", "--yesterday"])
        self.assertEqual(r.exit_code, 0, msg=r.output)
        self.assertNotIn("project rows can overlap attribution", r.output)

    def test_status_additive_partitions_sessions_and_hides_overlap_note(self):
        start = datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 22, 8, 30, tzinfo=timezone.utc)
        report = _FakeReport(
            project_reports={
                "A": {"2026-04-22": {"hours": 1.0, "sessions": [(start, end, [{"project": "A"}])]}},
                "B": {"2026-04-22": {"hours": 1.0, "sessions": [(start, end, [{"project": "B"}])]}},
            },
            overall_days={
                "2026-04-22": {
                    "hours": 1.0,
                    "sessions": [
                        (
                            start,
                            end,
                            [
                                {"project": "A", "source": "Cursor"},
                                {"project": "A", "source": "Cursor"},
                                {"project": "B", "source": "Cursor"},
                            ],
                        ),
                        (start, end, [{"project": "B", "source": "Cursor"}, {"project": "B", "source": "Cursor"}]),
                    ],
                }
            },
            included_events=[{"project": "A"}],
        )
        report.args = type("Args", (), {"min_session": 15, "min_session_passive": 5, "noise_profile": "strict"})()
        with patch("core.report_service.run_timelog_report", return_value=report):
            r = self.runner.invoke(app, ["status", "--yesterday", "--additive"])
        self.assertEqual(r.exit_code, 0, msg=r.output)
        self.assertIn("Hours Summary (", r.output)
        self.assertIn("additive", r.output)
        self.assertNotIn("project rows can overlap attribution", r.output)

    def test_status_prints_ultra_strict_note(self):
        report = _FakeReport(
            project_reports={"Project Alpha": {"2026-04-22": {"hours": 0.1, "sessions": [1]}}},
            overall_days={"2026-04-22": {"hours": 0.1, "sessions": [1]}},
            included_events=[{"project": "Project Alpha", "source": "Cursor"}],
        )
        report.args.noise_profile = "ultra-strict"
        with patch("core.report_service.run_timelog_report", return_value=report):
            r = self.runner.invoke(app, ["status", "--yesterday", "--noise-profile", "ultra-strict"])
        self.assertEqual(r.exit_code, 0, msg=r.output)
        self.assertIn("ultra-strict removes extra diagnostic/repository churn noise", r.output)

    def test_status_forwards_noise_profile(self):
        report = _FakeReport(
            project_reports={},
            overall_days={},
            included_events=[],
        )
        with patch("core.report_service.run_timelog_report", return_value=report) as run_mock:
            r = self.runner.invoke(app, ["status", "--yesterday", "--noise-profile", "ultra-strict"])
        self.assertEqual(r.exit_code, 0, msg=r.output)
        options = run_mock.call_args[0][3]
        self.assertEqual(getattr(options, "noise_profile", ""), "ultra-strict")
        self.assertIn("No activity tracked for this period.", r.output)
        self.assertIn("gittan doctor", r.output)
        self.assertIn("gittan report --today", r.output)
        self.assertIn("--source-summary", r.output)

    def test_status_forwards_lovable_noise_profile(self):
        report = _FakeReport(
            project_reports={},
            overall_days={},
            included_events=[],
        )
        with patch("core.report_service.run_timelog_report", return_value=report) as run_mock:
            r = self.runner.invoke(app, ["status", "--yesterday", "--lovable-noise-profile", "strict"])
        self.assertEqual(r.exit_code, 0, msg=r.output)
        options = run_mock.call_args[0][3]
        self.assertEqual(getattr(options, "lovable_noise_profile", ""), "strict")

    def test_status_accepts_alias_global_and_lovable_profile_flags(self):
        report = _FakeReport(
            project_reports={},
            overall_days={},
            included_events=[],
        )
        with patch("core.report_service.run_timelog_report", return_value=report) as run_mock:
            r = self.runner.invoke(
                app,
                ["status", "--yesterday", "--global-noise-profile", "ultra-strict", "--lovable-profile", "strict"],
            )
        self.assertEqual(r.exit_code, 0, msg=r.output)
        options = run_mock.call_args[0][3]
        self.assertEqual(getattr(options, "noise_profile", ""), "ultra-strict")
        self.assertEqual(getattr(options, "lovable_noise_profile", ""), "strict")


if __name__ == "__main__":
    unittest.main()
