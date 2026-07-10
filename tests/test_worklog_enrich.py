from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.worklog_enrich import (
    enrich_worklog_session_labels,
    is_commit_worklog_detail,
    is_pr_number_session_label,
    normalize_worklog_detail,
)
from tests.event_helpers import make_test_event


class WorklogEnrichTests(unittest.TestCase):
    def test_normalize_worklog_detail_strips_bullet_dash(self):
        self.assertEqual(normalize_worklog_detail("- Commit: fix export"), "Commit: fix export")

    def test_is_pr_number_session_label(self):
        self.assertTrue(is_pr_number_session_label("PR #347"))
        self.assertTrue(is_pr_number_session_label("pr #347: spike title"))
        self.assertTrue(is_pr_number_session_label("  PR#12: fix  "))
        self.assertFalse(is_pr_number_session_label("Restore agent labels"))
        self.assertFalse(is_pr_number_session_label("Discuss PR #347 later"))
        self.assertFalse(is_pr_number_session_label(""))
        self.assertFalse(is_pr_number_session_label(None))

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

    def test_enrich_skips_pr_number_shaped_session_labels(self):
        """GH-351: sticky Glass PR-tab titles must not paint delivery rows."""
        base = datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)
        events = [
            make_test_event(
                "Cursor (agent)",
                base,
                "reject sticky PR tab title (@work-unit-v2-spike-267)",
                "timelog-extract",
                anchors={"label": "PR #347: spike title"},
            ),
            make_test_event(
                "GitHub",
                base + timedelta(minutes=10),
                "issue #345 opened (example/project-alpha)",
                "timelog-extract",
            ),
            make_test_event(
                "TIMELOG.md",
                base + timedelta(minutes=12),
                "Commit: docs for overpaint guard",
                "timelog-extract",
            ),
        ]
        from core.worklog_enrich import enrich_delivery_session_labels

        enrich_delivery_session_labels(events)
        self.assertNotIn("label", events[1].get("anchors", {}))
        self.assertNotIn("label", events[2].get("anchors", {}))
        self.assertEqual(events[1]["detail"], "issue #345 opened (example/project-alpha)")

    def test_enrich_skips_shell_title_session_labels(self):
        """GH-361: terminal-title labels (shell names) must not paint delivery rows."""
        base = datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc)
        events = [
            make_test_event(
                "Cursor (agent)",
                base,
                "3 turns",
                "timelog-extract",
                anchors={"label": "zsh"},
            ),
            make_test_event(
                "GitHub",
                base + timedelta(minutes=10),
                "issue #361 opened (example/project-alpha)",
                "timelog-extract",
            ),
            make_test_event(
                "TIMELOG.md",
                base + timedelta(minutes=12),
                "Commit: guard terminal titles",
                "timelog-extract",
            ),
        ]
        from core.worklog_enrich import enrich_delivery_session_labels

        enrich_delivery_session_labels(events)
        self.assertNotIn("label", events[1].get("anchors", {}))
        self.assertNotIn("label", events[2].get("anchors", {}))

    def test_is_shell_title_session_label(self):
        from core.worklog_enrich import is_shell_title_session_label

        self.assertTrue(is_shell_title_session_label("zsh"))
        self.assertTrue(is_shell_title_session_label("  Bash  "))
        self.assertFalse(is_shell_title_session_label("zsh scripting tips"))
        self.assertFalse(is_shell_title_session_label("Restore agent labels"))
        self.assertFalse(is_shell_title_session_label(""))
        self.assertFalse(is_shell_title_session_label(None))

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

    def test_enrich_skips_uncategorized_rows(self):
        base = datetime(2026, 6, 24, 15, 40, tzinfo=timezone.utc)
        events = [
            make_test_event(
                "Cursor (agent)",
                base,
                "2 turns",
                "Uncategorized",
                anchors={"label": "Shared session title"},
            ),
            make_test_event(
                "GitHub",
                base + timedelta(minutes=5),
                "push to owner-a/project-beta",
                "Uncategorized",
            ),
        ]
        from core.worklog_enrich import enrich_delivery_session_labels

        enrich_delivery_session_labels(events, uncategorized="Uncategorized")
        self.assertNotIn("label", events[1].get("anchors", {}))


if __name__ == "__main__":
    unittest.main()
