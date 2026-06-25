"""Tests for per-session terminal preview (one line per source when possible)."""

import unittest
from datetime import datetime, timezone

from outputs.terminal_preview import (
    pick_session_preview_events,
    session_preview_omitted_summary,
)


class TerminalPreviewTests(unittest.TestCase):
    def test_shows_all_non_noise_events(self):
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
        picked = pick_session_preview_events(session, order)
        # Raw Cursor log lines (no label) are preview noise; evidence sources stay.
        self.assertEqual(len(picked), 2)
        self.assertEqual({e["source"] for e in picked}, {"GitHub", "Chrome"})

    def test_respects_max_lines_when_explicit(self):
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

    def test_footer_never_says_and_n_more_for_evidence(self):
        order = ["Cursor"]
        base = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
        session = [
            {
                "source": "Cursor",
                "local_ts": base,
                "project": "P",
                "detail": "real work",
            },
            {
                "source": "Cursor",
                "local_ts": base.replace(minute=1),
                "project": "P",
                "detail": "timelog-extract — hooks.json — noise",
            },
        ]
        picked = pick_session_preview_events(session, order)
        summary = session_preview_omitted_summary(session, picked)
        self.assertIsNotNone(summary)
        self.assertNotIn("more", summary.lower())
        self.assertIn("IDE log", summary)

    def test_always_shows_session_title_and_hides_cursor_log_noise(self):
        order = ["Cursor", "Chrome"]
        base = datetime(2026, 6, 11, 10, 36, tzinfo=timezone.utc)
        session = [
            {
                "source": "Cursor",
                "local_ts": base,
                "project": "timelog-extract",
                "detail": "timelog-extract — 2026-06-11 [info] > git --git-dir /x/.git",
            },
            {
                "source": "Cursor",
                "local_ts": base.replace(minute=58),
                "project": "timelog-extract",
                "detail": "Freelance bridge dashboard development",
                "anchors": {"label": "freelance bridge dashboard development"},
            },
            {
                "source": "Chrome",
                "local_ts": base.replace(minute=40),
                "project": "timelog-extract",
                "detail": "timelog-extract/docs/README.md",
            },
        ]
        picked = pick_session_preview_events(session, order, max_lines=12)
        details = [e["detail"] for e in picked]
        self.assertIn("Freelance bridge dashboard development", details)
        self.assertIn("timelog-extract/docs/README.md", details)
        self.assertTrue(all("git --git-dir" not in d for d in details))
        summary = session_preview_omitted_summary(session, picked)
        self.assertIsNotNone(summary)
        self.assertIn("IDE log", summary)

    def test_footer_skips_misleading_ide_label_when_evidence_also_hidden(self):
        order = ["A", "B"]
        base = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
        session = [
            {
                "source": "A",
                "local_ts": base.replace(minute=i),
                "project": "P",
                "detail": f"evidence-{i}",
            }
            for i in range(3)
        ] + [
            {
                "source": "Cursor",
                "local_ts": base.replace(minute=10),
                "project": "P",
                "detail": "timelog-extract — hooks.json — noise",
            }
        ]
        picked = pick_session_preview_events(session, order, max_lines=2)
        summary = session_preview_omitted_summary(session, picked)
        self.assertIsNone(summary)

    def test_high_signal_lovable_not_capped_by_noise(self):
        order = ["Lovable (desktop)", "Cursor"]
        base = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
        session = [
            {
                "source": "Lovable (desktop)",
                "local_ts": base,
                "project": "Uncategorized",
                "detail": "storage signal — https://uuid.lovableproject.com/",
            },
            {
                "source": "Cursor",
                "local_ts": base,
                "project": "timelog-extract",
                "detail": "timelog-extract — hooks.json — config",
            },
        ]
        picked = pick_session_preview_events(session, order, max_lines=12)
        self.assertEqual(len(picked), 1)
        self.assertEqual(picked[0]["source"], "Lovable (desktop)")


if __name__ == "__main__":
    unittest.main()
