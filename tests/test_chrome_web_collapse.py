"""Tests for tracked-web per-window heartbeat collapse (GH-414)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chrome_test_support import EPOCH_DELTA_US, insert_visit, make_chrome_db, make_event

from collectors.chrome import (
    WEB_VISIT_COLLAPSE_MINUTES,
    collect_claude_ai_urls,
    dedupe_web_visit_rows,
    web_visit_collapse_minutes,
)
from core.domain import compute_sessions

_NEUTRAL_TITLE = "project-alpha chat"
_CHAT_URL = "https://claude.ai/chat/abc123"


def _claude_results(home: Path, visits: list[datetime], collapse_minutes: int = WEB_VISIT_COLLAPSE_MINUTES):
    chrome_dir = home / "Library/Application Support/Google/Chrome/Default"
    chrome_dir.mkdir(parents=True)
    db_path = chrome_dir / "History"
    make_chrome_db(db_path)
    for ts in visits:
        insert_visit(db_path, _CHAT_URL, _NEUTRAL_TITLE, ts)
    dt_from = min(visits).replace(hour=0, minute=0, second=0, microsecond=0)
    dt_to = max(visits).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return collect_claude_ai_urls(
        [{"name": "project-alpha", "tracked_urls": ["claude.ai"]}],
        dt_from,
        dt_to,
        home=home,
        epoch_delta_us=EPOCH_DELTA_US,
        uncategorized="Uncategorized",
        make_event=make_event,
        collapse_minutes=collapse_minutes,
    )


class WebVisitCollapseTests(unittest.TestCase):
    def test_web_visit_collapse_minutes_reuses_chrome_cadence(self):
        self.assertEqual(web_visit_collapse_minutes(12), 12)
        self.assertEqual(web_visit_collapse_minutes(0), 0)
        self.assertEqual(web_visit_collapse_minutes(8), 8)

    def test_web_visit_collapse_minutes_clamps_below_session_gap(self):
        """High --chrome-collapse-minutes must not meet or exceed the session gap."""
        self.assertEqual(web_visit_collapse_minutes(15, session_gap_minutes=15), 14)
        self.assertEqual(web_visit_collapse_minutes(30, session_gap_minutes=15), 14)
        self.assertEqual(web_visit_collapse_minutes(12, session_gap_minutes=10), 9)
        self.assertEqual(web_visit_collapse_minutes(0, session_gap_minutes=15), 0)

    def test_dedupe_web_visit_rows_respects_zero_collapse_minutes(self):
        ts = datetime(2026, 4, 10, 4, 28, tzinfo=timezone.utc)
        ts_cu = int(ts.timestamp() * 1_000_000) + EPOCH_DELTA_US
        rows = [
            (ts_cu, _CHAT_URL, _NEUTRAL_TITLE),
            (ts_cu + 60_000_000, _CHAT_URL, _NEUTRAL_TITLE),
        ]
        self.assertEqual(len(dedupe_web_visit_rows(rows, 0, EPOCH_DELTA_US)), 2)
        self.assertEqual(len(dedupe_web_visit_rows(rows, WEB_VISIT_COLLAPSE_MINUTES, EPOCH_DELTA_US)), 1)

    def test_same_window_visits_collapse_to_one(self):
        """Visits within the cadence window collapse to a single heartbeat."""
        base = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            results = _claude_results(
                Path(tmpdir),
                [base, base + timedelta(minutes=5), base + timedelta(minutes=11)],
            )
            self.assertEqual(len(results), 1)

    def test_sustained_same_url_emits_periodic_heartbeats(self):
        """Multi-hour same-URL work yields multiple events, not one first-visit."""
        base = datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
        # Dense SPA-style revisits every 2 minutes for 3 hours (91 raw).
        # 12-min window → emit ≈ every 12 minutes → ~16 heartbeats.
        visits = [base + timedelta(minutes=2 * i) for i in range(91)]
        with tempfile.TemporaryDirectory() as tmpdir:
            results = _claude_results(Path(tmpdir), visits)
            self.assertGreater(len(results), 1)
            self.assertLess(len(results), len(visits))
            self.assertGreaterEqual(len(results), 14)
            self.assertLessEqual(len(results), 20)

    def test_sparse_one_off_visit_stays_single(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = _claude_results(
                Path(tmpdir),
                [datetime(2026, 4, 10, 14, 22, tzinfo=timezone.utc)],
            )
            self.assertEqual(len(results), 1)

    def test_claude_ai_midnight_boundary_keeps_both_calendar_days(self):
        """Visits 10 minutes apart across UTC midnight must not collapse to one event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = _claude_results(
                Path(tmpdir),
                [
                    datetime(2026, 4, 10, 23, 55, tzinfo=timezone.utc),
                    datetime(2026, 4, 11, 0, 5, tzinfo=timezone.utc),
                ],
            )
            self.assertEqual(len(results), 2)

    def test_sustained_heartbeats_form_one_session(self):
        """Periodic heartbeats stay inside one gap-clustered session (duration signal)."""
        base = datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
        # Dense revisits so emit spacing ≈ 12 min (< 15-min session gap).
        visits = [base + timedelta(minutes=2 * i) for i in range(61)]  # ~2h
        with tempfile.TemporaryDirectory() as tmpdir:
            results = _claude_results(Path(tmpdir), visits)
            self.assertGreaterEqual(len(results), 10)
            entries = [{"local_ts": event["ts"]} for event in results]
            sessions = compute_sessions(entries, gap_minutes=15)
            self.assertEqual(len(sessions), 1)
            start, end, _events = sessions[0]
            span_hours = (end - start).total_seconds() / 3600
            self.assertGreaterEqual(span_hours, 1.9)

    def test_high_collapse_minutes_still_forms_one_session(self):
        """Collapse >= gap still clamps heartbeats so one session forms."""
        gap = 15
        collapse = web_visit_collapse_minutes(30, session_gap_minutes=gap)
        self.assertLess(collapse, gap)
        base = datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
        # Dense revisits over ~2.5h; clamped cadence (~14 min) stays under gap.
        visits = [base + timedelta(minutes=2 * i) for i in range(76)]
        with tempfile.TemporaryDirectory() as tmpdir:
            results = _claude_results(Path(tmpdir), visits, collapse_minutes=collapse)
            self.assertGreaterEqual(len(results), 8)
            entries = [{"local_ts": event["ts"]} for event in results]
            sessions = compute_sessions(entries, gap_minutes=gap)
            self.assertEqual(len(sessions), 1)
            start, end, _events = sessions[0]
            span_hours = (end - start).total_seconds() / 3600
            self.assertGreaterEqual(span_hours, 1.9)


if __name__ == "__main__":
    unittest.main()
