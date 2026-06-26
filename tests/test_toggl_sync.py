"""Tests for Toggl time-entry candidate building, dedup, and posting."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# A home with no reported_time store, so observed-path tests never flip into
# Phase 3 reported-mode by reading the developer's real ~/.gittan.
_EMPTY_HOME = Path("/nonexistent-gittan-home-for-tests")

from typer.testing import CliRunner

from collectors.toggl import (
    TogglCredentials,
    post_toggl_time_entry,
    resolve_toggl_credentials,
    toggl_sync_enabled,
)
from core.cli import app
from core.cli_toggl_sync import _next_step_hint
from core.report_service import ReportPayload
from core.toggl_sync import (
    TogglEntryCandidate,
    TogglSyncSummary,
    build_toggl_entry_candidates,
)

TEST_TOKEN = "fake-token"


def _payload(overall_days, profiles):
    start = datetime(2026, 6, 23, 9, 0)
    end = datetime(2026, 6, 23, 17, 0)
    return ReportPayload(
        dt_from=start,
        dt_to=end,
        profiles=profiles,
        config_path=None,
        worklog_path=None,  # type: ignore[arg-type]
        all_events=[],
        included_events=[],
        grouped={},
        overall_days=overall_days,
        project_reports={},
        screen_time_days=None,
        collector_status={},
        args=Namespace(min_session=15, min_session_passive=5),
        source_strategy_effective="worklog-first",
    )


class CandidateBuildingTests(unittest.TestCase):
    def test_aggregates_per_project_per_day(self):
        start = datetime(2026, 6, 23, 10, 0)
        mid = datetime(2026, 6, 23, 11, 0)
        end = datetime(2026, 6, 23, 12, 0)
        events = [{"project": "Project Alpha", "source": "TIMELOG.md"}]
        payload = _payload(
            {
                "2026-06-23": {
                    "sessions": [(start, mid, events), (mid, end, events)],
                    "hours": 2.0,
                }
            },
            [{"name": "Project Alpha", "toggl_project_id": 123}],
        )
        candidates, unmapped = build_toggl_entry_candidates(payload, payload.profiles, _EMPTY_HOME)
        self.assertEqual(unmapped, 0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].project_id, 123)
        self.assertEqual(candidates[0].day, "2026-06-23")
        self.assertEqual(candidates[0].started, start)  # earliest start of the day
        self.assertGreater(candidates[0].seconds, 0)

    def test_unmapped_project_is_counted_not_posted(self):
        start = datetime(2026, 6, 23, 10, 0)
        end = datetime(2026, 6, 23, 11, 0)
        payload = _payload(
            {"2026-06-23": {"sessions": [(start, end, [{"project": "Project Beta"}])], "hours": 1.0}},
            [{"name": "Project Alpha", "toggl_project_id": 123}],
        )
        candidates, unmapped = build_toggl_entry_candidates(payload, payload.profiles, _EMPTY_HOME)
        self.assertEqual(candidates, [])
        self.assertEqual(unmapped, 1)

    def test_marker_tag_is_deterministic(self):
        candidate = TogglEntryCandidate(
            project_name="Project Alpha",
            project_id=123,
            day="2026-06-23",
            started=datetime(2026, 6, 23, 10, 0, tzinfo=timezone.utc),
            seconds=3600,
        )
        self.assertEqual(candidate.marker_tag, "gittan:123:2026-06-23")
        self.assertIn("gittan", candidate.tags)
        self.assertIn("gittan:123:2026-06-23", candidate.tags)


class ReportedModeTests(unittest.TestCase):
    """Phase 3: with confirmed reported_time in the window, sync posts those hours."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _confirm(self, project, day, hours, *, source="session", note="", state="confirmed"):
        from core.reported_time import ReportedTimeRecord, append_record

        origin = [] if source == "manual" else [f"{day}T0900"]
        append_record(
            ReportedTimeRecord(
                date=day, project=project, hours=hours, source=source,
                state=state, origin_ref=origin, note=note,
            ),
            home=self.home,
        )

    def test_uses_confirmed_hours_not_observed(self):
        # Observed says ~1h; confirmed reported says 5h — sync must post 5h.
        self._confirm("Project Alpha", "2026-06-23", 5.0)
        payload = _payload(
            {"2026-06-23": {"sessions": [(datetime(2026, 6, 23, 10, 0), datetime(2026, 6, 23, 11, 0), [{"project": "Project Alpha"}])], "hours": 1.0}},
            [{"name": "Project Alpha", "toggl_project_id": 123}],
        )
        candidates, unmapped = build_toggl_entry_candidates(payload, payload.profiles, self.home)
        self.assertEqual(unmapped, 0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].project_id, 123)
        self.assertEqual(candidates[0].seconds, 5 * 3600)

    def test_manual_time_with_no_session_is_posted(self):
        # Net-new manual time gittan never observed still posts (the undercount fix).
        self._confirm("Project Alpha", "2026-06-23", 3.0, source="manual", note="SFTP deploy")
        payload = _payload({}, [{"name": "Project Alpha", "toggl_project_id": 123}])
        candidates, unmapped = build_toggl_entry_candidates(payload, payload.profiles, self.home)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].seconds, 3 * 3600)

    def test_unmapped_project_counted_in_reported_mode(self):
        self._confirm("Project Beta", "2026-06-23", 2.0)
        payload = _payload({}, [{"name": "Project Alpha", "toggl_project_id": 123}])
        candidates, unmapped = build_toggl_entry_candidates(payload, payload.profiles, self.home)
        self.assertEqual(candidates, [])
        self.assertEqual(unmapped, 1)

    def test_proposed_only_falls_back_to_observed(self):
        # A proposed (not confirmed) record does not trigger reported-mode.
        self._confirm("Project Alpha", "2026-06-23", 5.0, state="proposed")
        observed_start = datetime(2026, 6, 23, 10, 0)
        payload = _payload(
            {"2026-06-23": {"sessions": [(observed_start, datetime(2026, 6, 23, 11, 0), [{"project": "Project Alpha"}])], "hours": 1.0}},
            [{"name": "Project Alpha", "toggl_project_id": 123}],
        )
        candidates, unmapped = build_toggl_entry_candidates(payload, payload.profiles, self.home)
        self.assertEqual(len(candidates), 1)
        # Observed start preserved (not the synthetic 09:00 of reported-mode).
        self.assertEqual(candidates[0].started, observed_start)


class CredentialGatingTests(unittest.TestCase):
    def test_disabled_when_off(self):
        ok, reason = toggl_sync_enabled(Namespace(toggl_sync="off"))
        self.assertFalse(ok)
        self.assertIn("off", reason)

    def test_requires_token_and_workspace(self):
        """Missing workspace id fails even when a token is passed on args."""
        with patch.dict(
            "os.environ",
            {"TOGGL_API_TOKEN": "", "TOGGL_WORKSPACE_ID": ""},
            clear=False,
        ):
            ok, reason = toggl_sync_enabled(
                Namespace(toggl_sync="on", toggl_api_token="t", toggl_workspace_id=None)
            )
        self.assertFalse(ok)
        self.assertIn("credentials missing", reason)

    def test_credentials_resolve_when_both_present(self):
        creds = resolve_toggl_credentials(
            Namespace(toggl_api_token="t", toggl_workspace_id="456")
        )
        self.assertIsNotNone(creds)
        self.assertEqual(creds.workspace_id, 456)


class PayloadFormatTests(unittest.TestCase):
    def test_start_uses_rfc3339_colon_offset(self):
        from datetime import timedelta, timezone as tz

        from collectors.toggl import build_time_entry_payload

        creds = TogglCredentials(api_token=TEST_TOKEN, workspace_id=1)
        start = datetime(2026, 6, 18, 14, 9, 49, tzinfo=tz(timedelta(hours=3)))
        payload = build_time_entry_payload(creds, start, 807, "x", 123, ["gittan"])
        # Toggl v9 rejects "+0300"; it requires the colon form "+03:00".
        self.assertEqual(payload["start"], "2026-06-18T14:09:49+03:00")

    def test_start_drops_microseconds(self):
        from datetime import timezone as tz

        from collectors.toggl import build_time_entry_payload

        creds = TogglCredentials(api_token=TEST_TOKEN, workspace_id=1)
        start = datetime(2026, 6, 18, 14, 9, 49, 123456, tzinfo=tz.utc)
        payload = build_time_entry_payload(creds, start, 60, "x", 123)
        self.assertEqual(payload["start"], "2026-06-18T14:09:49+00:00")


class PostClientTests(unittest.TestCase):
    def test_rejects_naive_start(self):
        creds = TogglCredentials(api_token=TEST_TOKEN, workspace_id=1)
        with self.assertRaises(RuntimeError):
            post_toggl_time_entry(
                creds=creds,
                start=datetime(2026, 6, 23, 10, 0),
                duration_seconds=3600,
                description="x",
                project_id=123,
            )

    def test_non_object_response_raises(self):
        from datetime import timezone as tz

        creds = TogglCredentials(api_token=TEST_TOKEN, workspace_id=1)
        start = datetime(2026, 6, 23, 10, 0, tzinfo=tz.utc)
        with patch("collectors.toggl._toggl_request", return_value=["unexpected"]):
            with self.assertRaises(RuntimeError):
                post_toggl_time_entry(
                    creds=creds, start=start, duration_seconds=60, description="x", project_id=123
                )


class CliTests(unittest.TestCase):
    def _creds(self):
        return TogglCredentials(api_token=TEST_TOKEN, workspace_id=1)

    def _candidate(self):
        return TogglEntryCandidate(
            project_name="Project Alpha",
            project_id=123,
            day="2026-06-23",
            started=datetime(2026, 6, 23, 10, 0, tzinfo=timezone.utc),
            seconds=7200,
        )

    def test_dry_run_posts_nothing(self):
        runner = CliRunner()
        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace(profiles=[])), patch(
            "core.cli_toggl_sync.toggl_sync_enabled", return_value=(True, "")
        ), patch("core.cli_toggl_sync.resolve_toggl_credentials", return_value=self._creds()), patch(
            "core.cli_toggl_sync.build_toggl_entry_candidates", return_value=([self._candidate()], 0)
        ), patch("core.cli_toggl_sync.post_candidate") as post:
            result = runner.invoke(app, ["toggl-sync", "--today", "--toggl-sync", "on", "--dry-run"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        post.assert_not_called()
        # Dry-run must print the exact outgoing payload (solo-first guardrail).
        self.assertIn('"created_with": "gittan"', result.output)
        self.assertIn('"project_id": 123', result.output)
        self.assertIn("posted=0, skipped=1", result.output)

    def test_dedup_skips_existing_marker(self):
        runner = CliRunner()
        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace(profiles=[], dt_from=datetime(2026, 6, 23), dt_to=datetime(2026, 6, 23))), patch(
            "core.cli_toggl_sync.toggl_sync_enabled", return_value=(True, "")
        ), patch("core.cli_toggl_sync.resolve_toggl_credentials", return_value=self._creds()), patch(
            "core.cli_toggl_sync.build_toggl_entry_candidates", return_value=([self._candidate()], 0)
        ), patch(
            "core.cli_toggl_sync.existing_marker_tags", return_value={"gittan:123:2026-06-23"}
        ) as marker, patch("core.cli_toggl_sync.post_candidate") as post:
            result = runner.invoke(app, ["toggl-sync", "--today", "--toggl-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        post.assert_not_called()
        self.assertIn("Skipped (already in Toggl)", result.output)
        # Toggl end_date is exclusive: must query through the day AFTER dt_to.
        _creds, start_date, end_date = marker.call_args.args
        self.assertEqual(start_date, "2026-06-23")
        self.assertEqual(end_date, "2026-06-24")
        self.assertIn("posted=0, skipped=1", result.output)

    def test_dedup_preflight_failure_aborts_without_posting(self):
        runner = CliRunner()
        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace(profiles=[], dt_from=datetime(2026, 6, 23), dt_to=datetime(2026, 6, 23))), patch(
            "core.cli_toggl_sync.toggl_sync_enabled", return_value=(True, "")
        ), patch("core.cli_toggl_sync.resolve_toggl_credentials", return_value=self._creds()), patch(
            "core.cli_toggl_sync.build_toggl_entry_candidates", return_value=([self._candidate()], 0)
        ), patch(
            "core.cli_toggl_sync.existing_marker_tags", side_effect=RuntimeError("Toggl down")
        ), patch("core.cli_toggl_sync.post_candidate") as post:
            result = runner.invoke(app, ["toggl-sync", "--today", "--toggl-sync", "on"])
        # Fail closed: no post attempted, non-zero exit.
        post.assert_not_called()
        self.assertNotEqual(result.exit_code, 0)

    def test_confirm_decline_skips(self):
        runner = CliRunner()
        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace(profiles=[], dt_from=datetime(2026, 6, 23), dt_to=datetime(2026, 6, 23))), patch(
            "core.cli_toggl_sync.toggl_sync_enabled", return_value=(True, "")
        ), patch("core.cli_toggl_sync.resolve_toggl_credentials", return_value=self._creds()), patch(
            "core.cli_toggl_sync.build_toggl_entry_candidates", return_value=([self._candidate()], 0)
        ), patch(
            "core.cli_toggl_sync.existing_marker_tags", return_value=set()
        ), patch("core.cli_toggl_sync.typer.confirm", return_value=False), patch(
            "core.cli_toggl_sync.post_candidate"
        ) as post:
            result = runner.invoke(app, ["toggl-sync", "--today", "--toggl-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        post.assert_not_called()
        self.assertIn("posted=0, skipped=1", result.output)

    def test_successful_post(self):
        runner = CliRunner()
        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace(profiles=[], dt_from=datetime(2026, 6, 23), dt_to=datetime(2026, 6, 23))), patch(
            "core.cli_toggl_sync.toggl_sync_enabled", return_value=(True, "")
        ), patch("core.cli_toggl_sync.resolve_toggl_credentials", return_value=self._creds()), patch(
            "core.cli_toggl_sync.build_toggl_entry_candidates", return_value=([self._candidate()], 0)
        ), patch(
            "core.cli_toggl_sync.existing_marker_tags", return_value=set()
        ), patch("core.cli_toggl_sync.typer.confirm", return_value=True), patch(
            "core.cli_toggl_sync.post_candidate", return_value="55555"
        ):
            result = runner.invoke(app, ["toggl-sync", "--today", "--toggl-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Posted Toggl time entry id=55555", result.output)
        self.assertIn("posted=1, skipped=0", result.output)


class NextStepHintTests(unittest.TestCase):
    def test_all_zero(self):
        self.assertIn("nothing to post", _next_step_hint(TogglSyncSummary()))

    def test_unmapped(self):
        self.assertIn("toggl_project_id", _next_step_hint(TogglSyncSummary(unmapped=2)))

    def test_failed_priority(self):
        hint = _next_step_hint(TogglSyncSummary(unmapped=1, failed=1))
        self.assertIn("token/workspace", hint)

    def test_posted(self):
        self.assertIn("verify the time entries", _next_step_hint(TogglSyncSummary(posted=1)))


if __name__ == "__main__":
    unittest.main()
