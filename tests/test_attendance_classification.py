import unittest
from datetime import datetime, timezone

from core.analytics import estimate_hours_by_day
from core.domain import (
    billable_total_hours,
    classify_attendance,
    compute_sessions,
    project_billable_raw_hours,
    session_duration_hours,
)
from core.sources import AI_SOURCES, DIRECT_WORK_EVIDENCE, GITHUB_SOURCE, get_source_role


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

    def test_legacy_windsurf_alias_stays_attended_direct_work(self):
        # Historical shadow-log / replay events still say "Windsurf".
        self.assertEqual(get_source_role("Windsurf"), DIRECT_WORK_EVIDENCE)
        events = [
            _make_event(
                "Windsurf",
                datetime(2026, 7, 2, 11, 0, tzinfo=timezone.utc),
                "Legacy log line",
                "P1",
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

    def test_classify_attendance_lovable_is_attended(self):
        # GH-313: Lovable (desktop) is an interactive AI builder -> attended,
        # not a cloud/background agent.
        events = [
            _make_event(
                "Lovable (desktop)",
                datetime(2026, 7, 2, 14, 0, tzinfo=timezone.utc),
                "Building the landing page",
                "P1",
            ),
        ]
        self.assertEqual(classify_attendance(events), "attended")

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


class TestBillableExcludesAgent(unittest.TestCase):
    """GH-284 slice 2: agent hours are not billable by default."""

    def _project(self):
        # One project, two days, with an attended/mixed/agent split.
        return {
            "2026-07-02": {"hours": 4.0, "attended_hours": 2.0, "mixed_hours": 1.0, "agent_hours": 1.0},
            "2026-07-03": {"hours": 2.0, "attended_hours": 1.0, "mixed_hours": 0.0, "agent_hours": 1.0},
        }

    def test_agent_hours_excluded_by_default(self):
        # total = 6.0, agent = 2.0 -> billable eligible = 4.0 (attended + mixed)
        self.assertAlmostEqual(project_billable_raw_hours(self._project()), 4.0)

    def test_agent_hours_included_when_opted_in(self):
        self.assertAlmostEqual(
            project_billable_raw_hours(self._project(), include_agent=True), 6.0
        )

    def test_all_agent_project_is_zero_billable(self):
        days = {"2026-07-02": {"hours": 3.0, "agent_hours": 3.0}}
        self.assertEqual(project_billable_raw_hours(days), 0.0)
        # ...but fully billable when opted in.
        self.assertAlmostEqual(project_billable_raw_hours(days, include_agent=True), 3.0)

    def test_missing_agent_key_stays_billable(self):
        # Uncertain/attended days have no agent_hours key -> full hours bill.
        days = {"2026-07-02": {"hours": 2.5}}
        self.assertAlmostEqual(project_billable_raw_hours(days), 2.5)

    def test_billable_rounding_applies_after_exclusion(self):
        # eligible 4.0h, unit 0.5 -> 4.0; eligible 4.0h with a 15-min unit stays 4.0
        eligible = project_billable_raw_hours(self._project())
        self.assertAlmostEqual(billable_total_hours(eligible, 0.5), 4.0)

    def test_invoice_note_makes_split_visible(self):
        from outputs.pdf import agent_attendance_note

        self.assertEqual(agent_attendance_note(0.0, False), "")
        excluded = agent_attendance_note(1.5, include_agent_billable=False)
        self.assertIn("Excludes 1.50 h", excluded)
        self.assertIn("not billable by default", excluded)
        included = agent_attendance_note(1.5, include_agent_billable=True)
        self.assertIn("Includes 1.50 h", included)
        self.assertIn("opted in", included)


class TestBillableExcludesPresence(unittest.TestCase):
    """GH-327: presence-signal hours are not billable by default."""

    def test_presence_hours_excluded_by_default(self):
        days = {
            "2026-07-09": {
                "hours": 5.0,
                "attended_hours": 5.0,
                "presence_hours": 3.0,
                "agent_hours": 0.0,
            }
        }
        # 5 - 3 presence = 2 authorship-eligible
        self.assertAlmostEqual(project_billable_raw_hours(days), 2.0)

    def test_presence_hours_included_when_opted_in(self):
        days = {
            "2026-07-09": {
                "hours": 5.0,
                "attended_hours": 5.0,
                "presence_hours": 3.0,
            }
        }
        self.assertAlmostEqual(
            project_billable_raw_hours(days, include_presence=True), 5.0
        )

    def test_agent_and_presence_both_excluded(self):
        days = {
            "2026-07-09": {
                "hours": 6.0,
                "attended_hours": 4.0,
                "agent_hours": 1.0,
                "presence_hours": 2.0,
            }
        }
        # 6 - 1 agent - 2 presence = 3
        self.assertAlmostEqual(project_billable_raw_hours(days), 3.0)
        self.assertAlmostEqual(
            project_billable_raw_hours(days, include_agent=True, include_presence=True),
            6.0,
        )

    def test_lovable_only_session_is_presence_hours(self):
        from core.sources import session_is_presence_signal_only

        events = [
            _make_event(
                "Lovable (desktop)",
                datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
                "cache ping",
                "P1",
            )
        ]
        self.assertTrue(session_is_presence_signal_only(events))
        self.assertEqual(classify_attendance(events), "attended")

    def test_cursor_plus_lovable_is_not_presence_only(self):
        from core.sources import session_is_presence_signal_only

        events = [
            _make_event(
                "Cursor",
                datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
                "edit",
                "P1",
            ),
            _make_event(
                "Lovable (desktop)",
                datetime(2026, 7, 9, 10, 5, tzinfo=timezone.utc),
                "cache",
                "P1",
            ),
        ]
        self.assertFalse(session_is_presence_signal_only(events))

    def test_presence_billable_note(self):
        from outputs.pdf import presence_billable_note

        self.assertEqual(presence_billable_note(0.0, False), "")
        excluded = presence_billable_note(1.25, include_presence_billable=False)
        self.assertIn("Excludes 1.25 h", excluded)
        self.assertIn("not billable by default", excluded)
        included = presence_billable_note(1.25, include_presence_billable=True)
        self.assertIn("Includes 1.25 h", included)


class TestBillableReportedLayer(unittest.TestCase):
    """GH-186 Phase 4: invoice/billable prefers confirmed reported_time."""

    def _reports(self):
        return {
            "Project Alpha": {
                "2026-07-02": {"hours": 4.0, "attended_hours": 3.0, "mixed_hours": 0.0, "agent_hours": 1.0},
            },
            "Project Beta": {
                "2026-07-02": {"hours": 2.0, "attended_hours": 2.0, "mixed_hours": 0.0, "agent_hours": 0.0},
            },
        }

    def test_fallback_to_observed_when_no_reported(self):
        from core.domain import billable_raw_by_project

        # No reported_time -> observed with agent excluded (Alpha 4-1=3, Beta 2).
        result = billable_raw_by_project(self._reports(), reported_hours=None)
        self.assertAlmostEqual(result["Project Alpha"], 3.0)
        self.assertAlmostEqual(result["Project Beta"], 2.0)

    def test_confirmed_reported_supersedes_observed(self):
        from core.domain import billable_raw_by_project

        # Human confirmed 5h for Alpha (incl. a manual addition) -> that wins, as-is.
        reported = {("Project Alpha", "2026-07-02"): 5.0}
        result = billable_raw_by_project(self._reports(), reported_hours=reported)
        self.assertAlmostEqual(result["Project Alpha"], 5.0)
        # Beta has no confirmed record in reported mode -> bills 0 (adoption switch).
        self.assertAlmostEqual(result["Project Beta"], 0.0)

    def test_reported_mode_ignores_agent_flag(self):
        from core.domain import billable_raw_by_project

        reported = {("Project Alpha", "2026-07-02"): 5.0}
        # include_agent_billable is irrelevant once confirmed hours are used.
        result = billable_raw_by_project(
            self._reports(), reported_hours=reported, include_agent_billable=True
        )
        self.assertAlmostEqual(result["Project Alpha"], 5.0)

    def test_reported_only_project_is_not_underbilled(self):
        from core.domain import billable_raw_by_project

        # "Manual Only" has confirmed/manual reported time but NO observed sessions,
        # so it is absent from project_reports. It must still appear in the billing
        # set (invoice/terminal iterate these values), never dropped.
        reported = {
            ("Project Alpha", "2026-07-02"): 4.0,
            ("Manual Only", "2026-07-03"): 1.5,
        }
        result = billable_raw_by_project(self._reports(), reported_hours=reported)
        self.assertAlmostEqual(result["Project Alpha"], 4.0)
        self.assertAlmostEqual(result["Manual Only"], 1.5)
        self.assertAlmostEqual(sum(result.values()), 5.5)


class TestSessionProjectLabels(unittest.TestCase):
    """GH-448: presence-only projects must not lead mixed-session titles."""

    def test_presence_only_project_sorted_after_authorship(self):
        from core.sources import session_project_labels

        events = [
            _make_event(
                "Cursor",
                datetime(2026, 7, 23, 16, 5, tzinfo=timezone.utc),
                "edit collectors",
                "timelog-extract",
            ),
            _make_event(
                "Chrome",
                datetime(2026, 7, 23, 16, 10, tzinfo=timezone.utc),
                "docs",
                "blueberry",
            ),
            _make_event(
                "Worklog",
                datetime(2026, 7, 23, 16, 20, tzinfo=timezone.utc),
                "notes",
                "timelog-extract",
            ),
            _make_event(
                "Lovable (desktop)",
                datetime(2026, 7, 23, 16, 43, tzinfo=timezone.utc),
                "Horse Haven — https://62146e85-26f9-4cf9-b3f2-601c44411dda.lovableproject.com/",
                "project-alpha",
            ),
        ]
        labels = session_project_labels(events)
        self.assertEqual(labels[0], "timelog-extract")
        self.assertIn("blueberry", labels)
        self.assertEqual(labels[-1], "project-alpha")
        # Alphabetical alone would put project-alpha first (capital P vs lowercase).
        self.assertNotEqual(labels[0], "project-alpha")

    def test_authorship_count_orders_before_alpha(self):
        from core.sources import session_project_labels

        events = [
            _make_event("Cursor", datetime(2026, 7, 23, 16, 1, tzinfo=timezone.utc), "a", "zebra"),
            _make_event("Cursor", datetime(2026, 7, 23, 16, 2, tzinfo=timezone.utc), "b", "zebra"),
            _make_event("Chrome", datetime(2026, 7, 23, 16, 3, tzinfo=timezone.utc), "c", "alpha"),
        ]
        self.assertEqual(session_project_labels(events), ["zebra", "alpha"])


if __name__ == "__main__":
    unittest.main()
