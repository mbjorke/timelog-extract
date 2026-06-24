"""Tests for versioned JSON truth payload."""

import unittest
from datetime import datetime, timedelta, timezone

from core.presence_estimated import compute_presence_estimated
from core.truth_payload import TRUTH_PAYLOAD_VERSION, build_truth_payload
from timelog_extract import estimate_hours_by_day, group_by_day


def _fake_session_duration(session_events, start_ts, end_ts, min_m, min_p):
    return (end_ts - start_ts).total_seconds() / 3600.0


class TruthPayloadTests(unittest.TestCase):
    def test_build_truth_payload_shape(self):
        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        events = [
            {
                "source": "TIMELOG.md",
                "timestamp": base,
                "detail": "A",
                "project": "Project A",
            },
        ]
        grouped = group_by_day(events)
        overall_days = estimate_hours_by_day(
            grouped,
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        day = base.astimezone().date().isoformat()
        payload = build_truth_payload(
            overall_days=overall_days,
            project_reports={"Project A": overall_days},
            included_events=events,
            collector_status={"TIMELOG.md": {"enabled": True, "reason": "", "events": 1}},
            screen_time_days=None,
            dt_from=base,
            dt_to=base + timedelta(hours=1),
            worklog_path="/tmp/TIMELOG.md",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            source_strategy_requested="auto",
            source_strategy_effective="worklog-first",
            primary_source="TIMELOG.md",
            session_duration_hours_fn=_fake_session_duration,
        )
        self.assertEqual(payload["schema"], "timelog_extract.truth_payload")
        self.assertEqual(payload["version"], TRUTH_PAYLOAD_VERSION)
        self.assertIn(day, payload["days"])
        self.assertIn("sessions", payload["days"][day])
        self.assertTrue(len(payload["days"][day]["sessions"]) >= 1)
        sess = payload["days"][day]["sessions"][0]
        self.assertIn("hours_estimated", sess)
        self.assertIn("events", sess)
        self.assertEqual(payload["settings"]["source_strategy_requested"], "auto")
        self.assertEqual(payload["settings"]["source_strategy_effective"], "worklog-first")
        self.assertEqual(payload["source_roles"]["primary_source"], "TIMELOG.md")

    def test_redacts_chrome_detail_when_chrome_raw(self):
        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        events = [
            {
                "source": "Chrome",
                "timestamp": base,
                "detail": "My tab title — https://example.com/secret-path",
                "project": "Uncategorized",
            },
        ]
        grouped = group_by_day(events)
        overall_days = estimate_hours_by_day(
            grouped,
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        day = base.astimezone().date().isoformat()
        payload = build_truth_payload(
            overall_days=overall_days,
            project_reports={"Uncategorized": overall_days},
            included_events=events,
            collector_status={"Chrome": {"enabled": True, "reason": "", "events": 1}},
            screen_time_days=None,
            dt_from=base,
            dt_to=base + timedelta(hours=1),
            worklog_path="/tmp/TIMELOG.md",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            source_strategy_requested="auto",
            source_strategy_effective="balanced",
            primary_source="balanced",
            session_duration_hours_fn=_fake_session_duration,
            chrome_raw=True,
        )
        self.assertTrue(payload["settings"].get("chrome_raw_json_detail_redacted"))
        sess = payload["days"][day]["sessions"][0]
        ev_out = sess["events"][0]
        self.assertEqual(ev_out["detail"], "My tab title")
        self.assertNotIn("example.com", ev_out["detail"])

    def test_redacts_url_only_chrome_detail_when_chrome_raw(self):
        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        events = [{"source": "Chrome", "timestamp": base, "detail": "https://example.org/only-url", "project": "U"}]
        grouped = group_by_day(events)
        overall_days = estimate_hours_by_day(grouped, gap_minutes=15, min_session_minutes=15, min_session_passive_minutes=5)
        day = base.astimezone().date().isoformat()
        payload = build_truth_payload(
            overall_days=overall_days,
            project_reports={"U": overall_days},
            included_events=events,
            collector_status={"Chrome": {"enabled": True, "reason": "", "events": 1}},
            screen_time_days=None,
            dt_from=base,
            dt_to=base + timedelta(hours=1),
            worklog_path="/tmp/TIMELOG.md",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            source_strategy_requested="auto",
            source_strategy_effective="balanced",
            primary_source="balanced",
            session_duration_hours_fn=_fake_session_duration,
            chrome_raw=True,
        )
        ev_out = payload["days"][day]["sessions"][0]["events"][0]
        self.assertTrue(payload["settings"].get("chrome_raw_json_detail_redacted"))
        self.assertEqual(ev_out["detail"], "Chrome visit")

    def test_truth_payload_includes_presence_estimated_when_available(self):
        base = datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc)
        later = datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc)
        events = [
            {"source": "Cursor", "timestamp": base, "local_ts": base, "detail": "a", "project": "P"},
            {"source": "Cursor", "timestamp": later, "local_ts": later, "detail": "b", "project": "P"},
        ]
        grouped = group_by_day(events)
        overall_days = estimate_hours_by_day(
            grouped, gap_minutes=15, min_session_minutes=15, min_session_passive_minutes=5
        )
        day = base.date().isoformat()
        project_reports = {"P": {day: {"hours": 1.0}}}
        presence = compute_presence_estimated(
            overall_days,
            project_reports,
            screen_time_days={day: 8 * 3600.0},
        )
        payload = build_truth_payload(
            overall_days=overall_days,
            project_reports=project_reports,
            included_events=events,
            collector_status={"Cursor": {"enabled": True, "reason": "", "events": 2}},
            screen_time_days={day: 8 * 3600.0},
            presence_estimated=presence,
            dt_from=base,
            dt_to=later,
            worklog_path="/tmp/TIMELOG.md",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            session_duration_hours_fn=_fake_session_duration,
        )
        self.assertIn("presence_estimated_hours", payload)
        self.assertEqual(payload["totals"]["hours_estimated"], payload["days"][day]["hours_estimated"])
        self.assertGreater(payload["presence_estimated_hours"]["total_hours"], 1.0)


if __name__ == "__main__":
    unittest.main()
