from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from core.events import filter_included_events, is_always_included_event


class EventFilterTests(unittest.TestCase):
    def test_lovable_desktop_uncategorized_is_always_included(self):
        event = {
            "source": "Lovable (desktop)",
            "timestamp": datetime(2026, 6, 11, 9, 48, tzinfo=timezone.utc),
            "detail": "storage signal — https://62146e85-26f9-4cf9-b3f2-601c44411dda.lovableproject.",
            "project": "Uncategorized",
        }
        self.assertTrue(is_always_included_event(event, "Uncategorized"))

    def test_filter_included_events_keeps_label_anchor_when_uncategorized_hidden(self):
        labeled = {
            "source": "Cursor",
            "timestamp": datetime(2026, 6, 11, 11, 58, tzinfo=timezone.utc),
            "detail": "Freelance bridge dashboard development",
            "project": "Uncategorized",
            "anchors": {"label": "freelance bridge dashboard development"},
        }
        args = SimpleNamespace(include_uncategorized=False, only_project=None, customer=None)
        included = filter_included_events([labeled], args, [], "Uncategorized")
        self.assertEqual(len(included), 1)

    def test_filter_included_events_keeps_lovable_when_uncategorized_hidden(self):
        lovable = {
            "source": "Lovable (desktop)",
            "timestamp": datetime(2026, 6, 11, 9, 48, tzinfo=timezone.utc),
            "detail": "storage signal — https://62146e85-26f9-4cf9-b3f2-601c44411dda.lovableproject.",
            "project": "Uncategorized",
        }
        cursor = {
            "source": "Cursor",
            "timestamp": datetime(2026, 6, 11, 9, 50, tzinfo=timezone.utc),
            "detail": "worktrees",
            "project": "Uncategorized",
        }
        args = SimpleNamespace(include_uncategorized=False, only_project=None, customer=None)
        included = filter_included_events([lovable, cursor], args, [], "Uncategorized")
        self.assertEqual(len(included), 1)
        self.assertEqual(included[0]["source"], "Lovable (desktop)")


if __name__ == "__main__":
    unittest.main()
