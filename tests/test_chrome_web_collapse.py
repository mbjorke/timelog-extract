"""Tests for daily dedupe on tracked web URL collectors."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.chrome import collect_claude_ai_urls

from chrome_test_support import EPOCH_DELTA_US, insert_visit, make_chrome_db, make_event


class WebVisitCollapseTests(unittest.TestCase):
    def test_claude_ai_daily_collapse_keeps_one_visit_per_url_per_day(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            chrome_dir = home / "Library/Application Support/Google/Chrome/Default"
            chrome_dir.mkdir(parents=True)
            db_path = chrome_dir / "History"
            make_chrome_db(db_path)
            insert_visit(
                db_path,
                "https://claude.ai/chat/abc123",
                "Akturo",
                datetime(2026, 4, 10, 4, 28, tzinfo=timezone.utc),
            )
            insert_visit(
                db_path,
                "https://claude.ai/chat/abc123",
                "Akturo",
                datetime(2026, 4, 10, 11, 28, tzinfo=timezone.utc),
            )
            insert_visit(
                db_path,
                "https://claude.ai/chat/abc123",
                "Akturo",
                datetime(2026, 4, 11, 4, 28, tzinfo=timezone.utc),
            )
            dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 4, 12, 0, 0, tzinfo=timezone.utc)
            results = collect_claude_ai_urls(
                [{"name": "Proj", "tracked_urls": ["claude.ai"]}],
                dt_from,
                dt_to,
                home=home,
                epoch_delta_us=EPOCH_DELTA_US,
                uncategorized="Uncategorized",
                make_event=make_event,
            )
            self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
