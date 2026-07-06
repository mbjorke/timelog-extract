import unittest
from datetime import datetime, timezone

from core.analytics import estimate_hours_by_day
from core.domain import classify_attendance, compute_sessions, session_duration_hours
from core.sources import AI_SOURCES, GITHUB_SOURCE


def _make_event(source, ts, detail, project):
    return {
        "source": source,
        "timestamp": ts,
        "detail": detail,
        "project": project,
        "local_ts": ts,  # Assuming local_ts == timestamp for simplicity in tests
    }


class TestAttendanceClassification(unittest.TestCase):
    def test_classify_attendance_agent_only(self):
        events = [
            _make_event(
                GITHUB_SOURCE, datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc), "Merge PR #1", "P1"
            ),
            _make_event(
                "Claude Code CLI", datetime(2026, 7, 2, 10, 5, tzinfo=timezone.utc), "Looping...", "P1"
            ),
        ]
        self.assertEqual(classify_attendance(events), "agent")

    def test_classify_attendance_attended_only(self):
        events = [
            _make_event(
                "Cursor", datetime(2026, 7, 2, 11, 0, tzinfo=timezone.utc), "Editing file", "P1"
            ),
            _make_event(
                "Chrome", datetime(2026, 7, 2, 11, 5, tzinfo=timezone.utc), "StackOverflow", "P1"
            ),
        ]
        self.assertEqual(classify_attendance(events), "attended")

    def test_classify_attendance_mixed(self):
        events = [
            _make_event("Cursor", datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc), "Editing", "P1"),
            _make_event(
                GITHUB_SOURCE, datetime(2026, 7, 2, 12, 10, tzinfo=timezone.utc), "Deploying", "P1"
            ),
        ]
        self.assertEqual(classify_attendance(events), "mixed")

    def test_classify_attendance_uncertain_defaults_to_attended(self):
        # Source not in either AGENT_SOURCES or ATTENDED_SOURCES
        events = [
            _make_event(
                "Unknown Source",
                datetime(2026, 7, 2, 13, 0, tzinfo=timezone.utc),
                "Doing something",
                "P1",
            ),
        ]
        self.assertEqual(classify_attendance(events), "attended")

    def test_estimate_hours_by_day_with_attendance(self):
        # AI_SOURCES in core.sources currently:
        # AI_SOURCES = {"Claude Code CLI", "Claude Desktop", ... "Cursor (agent)", ...}
        # "Cursor" is NOT in AI_SOURCES (it's in SOURCE_ROLES as DIRECT_WORK_EVIDENCE but not AI_SOURCES)
        # "Claude Code CLI" IS in AI_SOURCES.
        # "GitHub" is NOT in AI_SOURCES.

        # Default min_session_passive = 5m = 0.0833h
        # Default min_session = 15m = 0.25h

        events = [
            # Session 1: Agent only (Claude Code CLI -> AI source -> 15m floor = 0.25h)
            _make_event(
                "Claude Code CLI", datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc), "Agent work", "P1"
            ),
            # Session 2: Attended (Cursor -> NOT AI source -> 5m floor = 0.0833h)
            _make_event("Cursor", datetime(2026, 7, 2, 11, 0, tzinfo=timezone.utc), "User work", "P1"),
            # Session 3: Mixed (Cursor + Claude Code CLI -> AI source present -> 15m floor = 0.25h)
            _make_event("Cursor", datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc), "User work", "P1"),
            _make_event(
                "Claude Code CLI", datetime(2026, 7, 2, 12, 5, tzinfo=timezone.utc), "Agent work", "P1"
            ),
        ]

        def _session_dur(evs, start, end, min_s, min_p):
            return session_duration_hours(evs, start, end, min_s, min_p, AI_SOURCES)

        days = {"2026-07-02": events}
        per_day = estimate_hours_by_day(
            days,
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            compute_sessions_fn=compute_sessions,
            session_duration_hours_fn=_session_dur,
            classify_attendance_fn=classify_attendance,
        )

        day_data = per_day["2026-07-02"]
        self.assertEqual(len(day_data["sessions"]), 3)

        # Session 1: agent
        self.assertEqual(day_data["sessions"][0][3], "agent")
        # Session 2: attended
        self.assertEqual(day_data["sessions"][1][3], "attended")
        # Session 3: mixed
        self.assertEqual(day_data["sessions"][2][3], "mixed")

        # Session 1: 0.25h agent
        # Session 2: 0.0833h attended
        # Session 3: 0.25h mixed
        self.assertAlmostEqual(day_data["agent_hours"], 0.25)
        self.assertAlmostEqual(day_data["attended_hours"], 0.0833333333333, places=4)
        self.assertAlmostEqual(day_data["mixed_hours"], 0.25, places=4)
        self.assertAlmostEqual(day_data["hours"], 0.583333333, places=4)


if __name__ == "__main__":
    unittest.main()
