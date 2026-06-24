from __future__ import annotations

import unittest

from outputs.terminal_preview import event_detail_parts, format_event_detail as _format_event_detail


class TerminalAnchorDisplayTests(unittest.TestCase):
    def test_format_event_detail_prefixes_label_when_missing_from_detail(self):
        event = {
            "detail": "timelog-extract — git status",
            "anchors": {"label": "freelance bridge dashboard development"},
        }
        text = _format_event_detail(event)
        self.assertIn("freelance bridge dashboard development", text)
        self.assertIn("timelog-extract", text)
        self.assertIn(": ", text)

    def test_event_detail_parts_splits_label_and_detail(self):
        event = {
            "detail": "fix export regression",
            "anchors": {"label": "toggle integration progress"},
        }
        label, detail = event_detail_parts(event)
        self.assertEqual(label, "toggle integration progress")
        self.assertEqual(detail, "fix export regression")
        self.assertEqual(
            _format_event_detail(event),
            "toggle integration progress: fix export regression",
        )

    def test_format_event_detail_skips_duplicate_label(self):
        event = {
            "detail": "Freelance bridge dashboard development",
            "anchors": {"label": "freelance bridge dashboard development"},
        }
        self.assertEqual(_format_event_detail(event), event["detail"])


if __name__ == "__main__":
    unittest.main()
