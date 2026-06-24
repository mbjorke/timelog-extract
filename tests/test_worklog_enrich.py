from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.worklog_enrich import enrich_worklog_session_labels, is_commit_worklog_detail, normalize_worklog_detail
from tests.event_helpers import make_test_event


class WorklogEnrichTests(unittest.TestCase):
    def test_normalize_worklog_detail_strips_bullet_dash(self):
        self.assertEqual(normalize_worklog_detail("- Commit: fix export"), "Commit: fix export")

    def test_is_commit_worklog_detail(self):
        self.assertTrue(is_commit_worklog_detail("Commit: fix export"))
        self.assertTrue(is_commit_worklog_detail("- Commit: fix export"))
        self.assertFalse(is_commit_worklog_detail("manual note"))

    def test_enrich_attaches_nearest_prior_session_label(self):
        base = datetime(2026, 6, 24, 15, 40, tzinfo=timezone.utc)
        events = [
            make_test_event(
                "Claude Code CLI",
                base,
                "merge onboarding verify PR",
                "timelog-extract",
                anchors={"label": "Toggle integration progress"},
            ),
            make_test_event(
                "TIMELOG.md",
                base + timedelta(minutes=10),
                "Commit: Unify session title display",
                "timelog-extract",
            ),
        ]
        enrich_worklog_session_labels(events)
        worklog = events[1]
        self.assertEqual(worklog["anchors"]["label"], "Toggle integration progress")
        self.assertEqual(worklog["detail"], "Commit: Unify session title display")

    def test_enrich_github_attaches_nearest_prior_session_label(self):
        base = datetime(2026, 6, 24, 15, 34, tzinfo=timezone.utc)
        events = [
            make_test_event(
                "Cursor (agent)",
                base,
                "6 turns",
                "timelog-extract",
                anchors={"label": "Configuration issues with Toggl and Jira"},
            ),
            make_test_event(
                "GitHub",
                base + timedelta(minutes=16),
                "push to mbjorke/timelog-extract (0 commits, ref claude-session-label)",
                "timelog-extract",
            ),
        ]
        events[1]["_github_user"] = "mbjorke"
        from core.worklog_enrich import enrich_github_session_labels

        enrich_github_session_labels(events)
        self.assertEqual(
            events[1]["anchors"]["label"],
            "Configuration issues with Toggl and Jira",
        )

    def test_enrich_skips_when_project_differs(self):
        base = datetime(2026, 6, 24, 15, 40, tzinfo=timezone.utc)
        events = [
            make_test_event(
                "Cursor (agent)",
                base,
                "2 turns",
                "project-alpha",
                anchors={"label": "Alpha dashboard"},
            ),
            make_test_event(
                "TIMELOG.md",
                base + timedelta(minutes=5),
                "Commit: docs",
                "timelog-extract",
            ),
        ]
        enrich_worklog_session_labels(events)
        self.assertNotIn("label", events[1].get("anchors", {}))


if __name__ == "__main__":
    unittest.main()
