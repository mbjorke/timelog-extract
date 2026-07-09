from __future__ import annotations

import unittest

from outputs.terminal_preview import event_detail_parts, format_event_detail as _format_event_detail


class TerminalAnchorDisplayTests(unittest.TestCase):
    def test_format_event_detail_prefixes_label_when_missing_from_detail(self):
        event = {
            "detail": "timelog-extract — git status",
            "anchors": {"label": "Freelance bridge dashboard development"},
        }
        text = _format_event_detail(event)
        self.assertIn("Freelance bridge dashboard development", text)
        self.assertIn("timelog-extract", text)
        self.assertIn(": ", text)

    def test_event_detail_parts_splits_label_and_detail(self):
        event = {
            "detail": "fix export regression",
            "anchors": {"label": "Toggle integration progress"},
        }
        label, detail = event_detail_parts(event)
        self.assertEqual(label, "Toggle integration progress")
        self.assertEqual(detail, "fix export regression")
        self.assertEqual(
            _format_event_detail(event),
            "Toggle integration progress: fix export regression",
        )

    def test_event_detail_parts_strips_redundant_cursor_title(self):
        event = {
            "detail": "Configuration issues with Toggl and Jira · 14 turns · timelog-extract",
            "anchors": {"label": "Configuration issues with Toggl and Jira"},
        }
        label, detail = event_detail_parts(event)
        self.assertEqual(label, "Configuration issues with Toggl and Jira")
        self.assertEqual(detail, "14 turns · timelog-extract")

    def test_event_detail_parts_worklog_uses_comma_separator(self):
        event = {
            "source": "TIMELOG.md",
            "detail": "Commit: Unify session title display",
            "anchors": {"label": "Toggle integration progress"},
        }
        self.assertEqual(
            _format_event_detail(event),
            "Toggle integration progress, Commit: Unify session title display",
        )

    def test_event_detail_parts_title_only_shows_label_without_colon(self):
        event = {
            "detail": "Freelance bridge dashboard development",
            "anchors": {"label": "Freelance bridge dashboard development"},
        }
        label, detail = event_detail_parts(event)
        self.assertEqual(label, "Freelance bridge dashboard development")
        self.assertEqual(detail, "")
        self.assertEqual(_format_event_detail(event), "Freelance bridge dashboard development")

    def test_format_event_detail_skips_duplicate_label(self):
        event = {
            "detail": "Freelance bridge dashboard development",
            "anchors": {"label": "Freelance bridge dashboard development"},
        }
        self.assertEqual(_format_event_detail(event), event["detail"])

    def test_mail_subject_label_and_recipient_detail(self):
        event = {
            "source": "Apple Mail",
            "detail": "customer-a@customer-a.test",
            "anchors": {"label": "Re: invoice Q2"},
        }
        self.assertEqual(_format_event_detail(event), "Re: invoice Q2: customer-a@customer-a.test")

    def test_calendar_title_label_and_calendar_hours_detail(self):
        event = {
            "source": "Calendar",
            "detail": "[Work] 1.00h",
            "anchors": {"label": "Standup with team"},
        }
        self.assertEqual(_format_event_detail(event), "Standup with team: [Work] 1.00h")

    def test_event_detail_parts_hides_label_when_same_as_project(self):
        event = {
            "project": "timelog-extract",
            "detail": "Start multitasking",
            "anchors": {"label": "timelog-extract", "dir": "timelog-extract"},
        }
        label, detail = event_detail_parts(event)
        self.assertEqual(label, "")
        self.assertEqual(detail, "Start multitasking")
        self.assertEqual(_format_event_detail(event), "Start multitasking")

    def test_event_detail_parts_keeps_distinct_composer_title(self):
        event = {
            "project": "timelog-extract",
            "detail": "how is it going?",
            "anchors": {"label": "Timely API insights"},
        }
        label, detail = event_detail_parts(event)
        self.assertEqual(label, "Timely API insights")
        self.assertEqual(detail, "how is it going?")


if __name__ == "__main__":
    unittest.main()
