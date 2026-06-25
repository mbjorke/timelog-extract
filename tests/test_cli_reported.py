"""Tests for `gittan reported` (review / add / list) — Part 2, Phase 2."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from core import reported_time as rt
from core.cli import app
from core.reported_sync import build_reported_proposals


def _temp_store():
    """Patch the reported_time store dir to a fresh temp dir."""
    tmp = tempfile.TemporaryDirectory()
    p = patch.object(rt, "reported_base_dir", return_value=Path(tmp.name) / "reported")
    return tmp, p


class BuildProposalsTests(unittest.TestCase):
    def test_aggregates_per_project_day(self):
        start = datetime(2026, 6, 18, 10, 0)
        mid = datetime(2026, 6, 18, 11, 0)
        end = datetime(2026, 6, 18, 12, 0)
        evs = [{"project": "Alpha", "source": "TIMELOG.md"}]
        report = SimpleNamespace(
            overall_days={"2026-06-18": {"sessions": [(start, mid, evs), (mid, end, evs)]}},
            args=Namespace(min_session=15, min_session_passive=5),
        )
        proposals = build_reported_proposals(report)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].project, "Alpha")
        self.assertEqual(proposals[0].state, "proposed")
        self.assertEqual(proposals[0].source, "session")
        self.assertGreater(proposals[0].hours, 0)
        self.assertEqual(len(proposals[0].origin_ref), 2)


class AddCommandTests(unittest.TestCase):
    def test_add_writes_manual_confirmed_record(self):
        tmp, store = _temp_store()
        with tmp, store:
            result = CliRunner().invoke(app, [
                "reported", "add", "--project", "ax-finans", "--date", "2026-06-18",
                "--hours", "3", "--note", "SFTP + server work",
            ])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            recs = rt.query(project="ax-finans", date="2026-06-18", states={"confirmed"})
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0].source, "manual")
            self.assertEqual(recs[0].hours, 3.0)
            self.assertEqual(recs[0].origin_ref, [])
            self.assertIn("SFTP", recs[0].note)

    def test_add_rejects_empty_note(self):
        tmp, store = _temp_store()
        with tmp, store:
            result = CliRunner().invoke(app, [
                "reported", "add", "--project", "P", "--date", "2026-06-18",
                "--hours", "2", "--note", "   ",
            ])
        self.assertNotEqual(result.exit_code, 0)

    def test_add_with_issue_sets_issue_key(self):
        tmp, store = _temp_store()
        with tmp, store:
            result = CliRunner().invoke(app, [
                "reported", "add", "--project", "P", "--date", "2026-06-18",
                "--hours", "2", "--note", "phone call", "--issue", "KAN-9",
            ])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            recs = rt.query(project="P", date="2026-06-18", states={"confirmed"})
            self.assertEqual(recs[0].issue_key, "KAN-9")

    def test_add_rejects_malformed_issue(self):
        tmp, store = _temp_store()
        with tmp, store:
            result = CliRunner().invoke(app, [
                "reported", "add", "--project", "P", "--date", "2026-06-18",
                "--hours", "2", "--note", "x", "--issue", "not a key",
            ])
        self.assertNotEqual(result.exit_code, 0)


class ReviewCommandTests(unittest.TestCase):
    def _proposal(self):
        return rt.ReportedTimeRecord(
            date="2026-06-18", project="Alpha", hours=2.5, source="session",
            state="proposed", origin_ref=["2026-06-18T1000"],
        )

    def test_dry_run_writes_nothing(self):
        tmp, store = _temp_store()
        with tmp, store, patch("core.report_service.run_timelog_report", return_value=SimpleNamespace()), patch(
            "core.cli_reported.build_reported_proposals", return_value=[self._proposal()]
        ):
            result = CliRunner().invoke(app, ["reported", "review", "--today", "--dry-run"])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertEqual(rt.query(), [])

    def test_confirm_writes_confirmed_record(self):
        tmp, store = _temp_store()
        with tmp, store, patch("core.report_service.run_timelog_report", return_value=SimpleNamespace()), patch(
            "core.cli_reported.build_reported_proposals", return_value=[self._proposal()]
        ), patch("core.cli_reported.typer.prompt", return_value="c"):
            result = CliRunner().invoke(app, ["reported", "review", "--today"])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            recs = rt.query(states={"confirmed"})
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0].project, "Alpha")
            self.assertIn("confirmed=1", result.output)

    def test_already_confirmed_is_skipped(self):
        tmp, store = _temp_store()
        with tmp, store:
            rt.append_record(rt.ReportedTimeRecord(
                date="2026-06-18", project="Alpha", hours=2.5, source="session",
                state="confirmed", origin_ref=["x"]))
            with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace()), patch(
                "core.cli_reported.build_reported_proposals", return_value=[self._proposal()]
            ), patch("core.cli_reported.typer.prompt") as prompt:
                result = CliRunner().invoke(app, ["reported", "review", "--today"])
            prompt.assert_not_called()
            self.assertIn("already=1", result.output)


class SyncCommandTests(unittest.TestCase):
    def _proposal(self, project):
        return rt.ReportedTimeRecord(
            date="2026-06-18", project=project, hours=2.5, source="session",
            state="proposed", origin_ref=["2026-06-18T1000"],
        )

    def test_auto_reports_optin_project(self):
        tmp, store = _temp_store()
        report = SimpleNamespace(profiles=[{"name": "Alpha", "auto_report": True}])
        with tmp, store, patch("core.report_service.run_timelog_report", return_value=report), patch(
            "core.cli_reported.build_reported_proposals", return_value=[self._proposal("Alpha")]
        ):
            result = CliRunner().invoke(app, ["reported", "sync", "--today"])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Auto-reported 1", result.output)
            recs = rt.query(states={"confirmed"})
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0].project, "Alpha")

    def test_non_optin_writes_nothing_and_nudges(self):
        tmp, store = _temp_store()
        report = SimpleNamespace(profiles=[{"name": "Beta"}])
        with tmp, store, patch("core.report_service.run_timelog_report", return_value=report), patch(
            "core.cli_reported.build_reported_proposals", return_value=[self._proposal("Beta")]
        ):
            result = CliRunner().invoke(app, ["reported", "sync", "--today"])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertEqual(rt.query(), [])
            self.assertIn("1 left for review", result.output)
            self.assertIn("auto_report", result.output)

    def test_dry_run_writes_nothing(self):
        tmp, store = _temp_store()
        report = SimpleNamespace(profiles=[{"name": "Alpha", "auto_report": True}])
        with tmp, store, patch("core.report_service.run_timelog_report", return_value=report), patch(
            "core.cli_reported.build_reported_proposals", return_value=[self._proposal("Alpha")]
        ):
            result = CliRunner().invoke(app, ["reported", "sync", "--today", "--dry-run"])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Would auto-report 1", result.output)
            self.assertEqual(rt.query(), [])

    def test_sibling_issue_not_skipped_as_already_reported(self):
        # Phase 3b dedup must be issue-aware: a reported KAN-2 must not skip KAN-3
        # on the same project+day (CodeRabbit #196).
        tmp, store = _temp_store()
        report = SimpleNamespace(profiles=[{"name": "Alpha", "auto_report": True}])
        p2 = rt.ReportedTimeRecord(date="2026-06-18", project="Alpha", hours=2.0, source="session",
                                   state="proposed", origin_ref=["2026-06-18T1000"], issue_key="KAN-2")
        p3 = rt.ReportedTimeRecord(date="2026-06-18", project="Alpha", hours=3.0, source="session",
                                   state="proposed", origin_ref=["2026-06-18T1100"], issue_key="KAN-3")
        with tmp, store:
            rt.append_record(rt.ReportedTimeRecord(
                date="2026-06-18", project="Alpha", hours=2.0, source="session",
                state="confirmed", origin_ref=["2026-06-18T1000"], issue_key="KAN-2"))
            with patch("core.report_service.run_timelog_report", return_value=report), patch(
                "core.cli_reported.build_reported_proposals", return_value=[p2, p3]
            ):
                result = CliRunner().invoke(app, ["reported", "sync", "--today"])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            confirmed = {(r.project, r.issue_key) for r in rt.query(states={"confirmed"})}
            self.assertEqual(confirmed, {("Alpha", "KAN-2"), ("Alpha", "KAN-3")})
            self.assertIn("Auto-reported 1", result.output)


if __name__ == "__main__":
    unittest.main()
