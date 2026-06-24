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


if __name__ == "__main__":
    unittest.main()
