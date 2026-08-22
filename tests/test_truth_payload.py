"""Tests for versioned JSON truth payload."""

import unittest
from datetime import datetime, timedelta, timezone

from core import truth_payload
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

    def test_session_attendance_from_overall_days_tuple(self):
        base = datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)
        end = base + timedelta(hours=1)
        events = [
            {"source": "Claude Code CLI", "timestamp": base, "detail": "x", "project": "P"},
            {"source": "Cursor", "timestamp": end, "detail": "y", "project": "P"},
        ]
        day = base.date().isoformat()
        overall_days = {
            day: {
                "entries": events,
                "sessions": [(base, end, events, "mixed")],
                "hours": 1.0,
                "attended_hours": 0.0,
                "mixed_hours": 1.0,
                "agent_hours": 0.0,
            }
        }
        payload = build_truth_payload(
            overall_days=overall_days,
            project_reports={"P": {day: {"hours": 1.0}}},
            included_events=events,
            collector_status={},
            screen_time_days=None,
            dt_from=base,
            dt_to=end,
            worklog_path="/tmp/TIMELOG.md",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            session_duration_hours_fn=_fake_session_duration,
        )
        self.assertEqual(payload["days"][day]["sessions"][0]["attendance"], "mixed")

    def test_per_project_worklog_metadata(self):
        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        payload = build_truth_payload(
            overall_days={},
            project_reports={},
            included_events=[],
            collector_status={},
            screen_time_days=None,
            dt_from=base,
            dt_to=base + timedelta(hours=1),
            worklog_path="/tmp/should-not-win.md",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            source_strategy_requested="auto",
            source_strategy_effective="per-project",
            primary_source="per-project",
            worklog_paths=["/tmp/client-a.md", "/tmp/client-b.md"],
            session_duration_hours_fn=_fake_session_duration,
        )
        self.assertEqual(payload["source_roles"]["mode"], "per-project")
        self.assertEqual(payload["source_roles"]["primary_source"], "per-project")
        self.assertEqual(payload["paths"]["worklog"], "")
        self.assertEqual(
            payload["paths"]["worklogs"],
            ["/tmp/client-a.md", "/tmp/client-b.md"],
        )

    def test_per_project_worklog_metadata_empty_worklogs(self):
        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        payload = build_truth_payload(
            overall_days={},
            project_reports={},
            included_events=[],
            collector_status={},
            screen_time_days=None,
            dt_from=base,
            dt_to=base + timedelta(hours=1),
            worklog_path="",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            source_strategy_effective="per-project",
            primary_source="per-project",
            worklog_paths=[],
            session_duration_hours_fn=_fake_session_duration,
        )
        self.assertEqual(payload["paths"]["worklogs"], [])
        self.assertEqual(payload["paths"]["worklog"], "")

    def test_derived_session_label_serialization_in_truth_payload(self):
        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        events = [
            {
                "source": "TIMELOG.md",
                "timestamp": base,
                "detail": "Commit: fix bug",
                "project": "Project A",
                "derived_session_label": True,
            },
            {
                "source": "Cursor",
                "timestamp": base,
                "detail": "Coding",
                "project": "Project A",
            }
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
            collector_status={},
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
        evs = payload["days"][day]["sessions"][0]["events"]
        self.assertTrue(evs[0]["derived_session_label"])
        self.assertFalse(evs[1]["derived_session_label"])


if __name__ == "__main__":
    unittest.main()


class SessionProjectHoursTests(unittest.TestCase):
    """A session spans every project touched between two 15-minute gaps.

    Consumers that read ``projects[0]`` as *the* project put the whole block on
    one row, which is the GH-544 failure: hours land on another project and
    often another customer. The payload now carries the split the report's own
    totals are built from.
    """

    def _payload(self, events):
        from core.domain import session_duration_hours
        from core.sources import AI_SOURCES

        return truth_payload._serialize_session(
            events[0]["local_ts"],
            events[-1]["local_ts"],
            events,
            session_duration_hours_fn=(
                lambda se, st, en, mn, mp: session_duration_hours(se, st, en, mn, mp, AI_SOURCES)
            ),
            min_session_minutes=15,
            min_session_passive_minutes=5,
            session_index=0,
            day="2026-08-21",
        )

    def _event(self, minute, project, source="Cursor", detail="work"):
        return {
            "local_ts": datetime(2026, 8, 21, 9, minute, tzinfo=timezone.utc),
            "timestamp": datetime(2026, 8, 21, 9, minute, tzinfo=timezone.utc),
            "source": source,
            "detail": detail,
            "project": project,
        }

    def test_a_single_project_session_puts_all_hours_on_it(self):
        events = [self._event(0, "alpha"), self._event(20, "alpha")]
        out = self._payload(events)
        self.assertEqual(list(out["project_hours"]), ["alpha"])
        self.assertAlmostEqual(out["project_hours"]["alpha"], out["hours_estimated"], places=6)

    def test_a_mixed_session_splits_rather_than_naming_one_project(self):
        events = [self._event(0, "alpha"), self._event(10, "beta"), self._event(20, "beta")]
        out = self._payload(events)
        self.assertEqual(sorted(out["project_hours"]), ["alpha", "beta"])
        self.assertGreater(out["project_hours"]["beta"], 0)

    def test_the_split_never_exceeds_the_session_total(self):
        events = [self._event(0, "alpha"), self._event(10, "beta"), self._event(20, "gamma")]
        out = self._payload(events)
        self.assertLessEqual(
            round(sum(out["project_hours"].values()), 6),
            round(out["hours_estimated"], 6) + 1e-6,
        )

    def test_projects_list_and_split_name_the_same_projects(self):
        events = [self._event(0, "alpha"), self._event(10, "beta")]
        out = self._payload(events)
        self.assertEqual(set(out["project_hours"]), set(out["projects"]))

    def test_the_split_matches_what_the_report_credits(self):
        """The payload must not carry a second, disagreeing number.

        Allocation is sensitive to its inputs: omitting the duration function
        let the allocator fall back to its own default, and the split stopped
        summing to the report -- 7.98 h against a reported 5.50 h on one
        project. The two must be built from the same call.
        """
        from core.domain import session_duration_hours
        from core.project_hours import allocate_session_hours_by_project

        events = [self._event(0, "alpha"), self._event(10, "beta"), self._event(20, "beta")]
        out = self._payload(events)

        expected = allocate_session_hours_by_project(
            events,
            out["hours_estimated"],
            session_duration_hours_fn=session_duration_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            gap_minutes=15,
        )
        self.assertEqual(
            {k: round(v, 6) for k, v in sorted(expected.items())},
            out["project_hours"],
        )


class EventAnchorsTests(unittest.TestCase):
    """The payload must carry why an hour was attributed, not only that it was."""

    def _event(self, anchors=None):
        from core.truth_payload import _serialize_event

        ev = {
            "source": "Cursor",
            "timestamp": datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc),
            "detail": "work",
            "project": "project-alpha",
        }
        if anchors is not None:
            ev["anchors"] = anchors
        return _serialize_event(ev)

    def test_anchors_reach_the_payload(self):
        out = self._event({"repo": "owner-example/widgets", "branch": "main"})
        self.assertEqual(
            out["anchors"], {"repo": "owner-example/widgets", "branch": "main"}
        )

    def test_an_event_without_anchors_carries_no_key(self):
        # Absent rather than an empty map: a consumer must be able to tell
        # "nothing anchored this" from "anchored to nothing".
        self.assertNotIn("anchors", self._event())
        self.assertNotIn("anchors", self._event({}))

    def test_empty_anchor_values_are_dropped(self):
        out = self._event({"repo": "owner-example/widgets", "dir": "", "branch": None})
        self.assertEqual(out["anchors"], {"repo": "owner-example/widgets"})

    def test_the_version_names_the_new_field(self):
        self.assertEqual(TRUTH_PAYLOAD_VERSION, "4")
