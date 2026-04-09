"""Tests for per-session terminal preview (one line per source when possible)."""

import unittest
from datetime import datetime, timezone

from outputs.terminal import pick_session_preview_events


class TerminalPreviewTests(unittest.TestCase):
    def test_one_line_per_source_before_fill(self):
        order = ["Cursor", "Chrome", "GitHub"]
        base = datetime(2026, 4, 9, 7, 0, tzinfo=timezone.utc)
        session = [
            {
                "source": "Cursor",
                "local_ts": base,
                "project": "P",
                "detail": "c1",
            },
            {
                "source": "Cursor",
                "local_ts": base.replace(minute=5),
                "project": "P",
                "detail": "c2",
            },
            {
                "source": "GitHub",
                "local_ts": base.replace(minute=10),
                "project": "P",
                "detail": "g1",
            },
            {
                "source": "Chrome",
                "local_ts": base.replace(minute=1),
                "project": "P",
                "detail": "ch1",
            },
        ]
        picked = pick_session_preview_events(session, order, max_lines=5)
        sources_in_order = [e["source"] for e in picked[:3]]
        self.assertIn("Cursor", sources_in_order)
        self.assertIn("Chrome", sources_in_order)
        self.assertIn("GitHub", sources_in_order)

    def test_respects_max_lines(self):
        order = ["A", "B", "C"]
        base = datetime(2026, 4, 9, 7, 0, tzinfo=timezone.utc)
        session = []
        for i in range(10):
            session.append(
                {
                    "source": "A",
                    "local_ts": base.replace(minute=i),
                    "project": "P",
                    "detail": f"d{i}",
                }
            )
        picked = pick_session_preview_events(session, order, max_lines=3)
        self.assertEqual(len(picked), 3)


if __name__ == "__main__":
    unittest.main()
