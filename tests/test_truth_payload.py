"""Tests for versioned JSON truth payload."""

from datetime import datetime, timedelta, timezone
import unittest

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


if __name__ == "__main__":
    unittest.main()
