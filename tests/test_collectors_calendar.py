from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.calendar import (
    DEFAULT_ROLE,
    ROLE_PRIMARY_CLAIM,
    ROLE_SCHEDULED_CONTEXT,
    calendar_db_path,
    collect_calendar,
    detect_calendar_db,
    parse_calendar_roles,
)

_COCOA_EPOCH_UNIX = datetime(2001, 1, 1, tzinfo=timezone.utc).timestamp()


def _make_event(source, ts, detail, project):
    return {"source": source, "timestamp": ts, "detail": detail, "project": project}


def _to_cocoa(dt: datetime) -> float:
    return dt.astimezone(timezone.utc).timestamp() - _COCOA_EPOCH_UNIX


def _write_calendar_db(home: Path, rows: list[dict]) -> None:
    """Create a minimal Calendar.sqlitedb fixture with the columns we read."""
    db = calendar_db_path(home)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE Calendar (ROWID INTEGER PRIMARY KEY, title TEXT)")
        conn.execute(
            "CREATE TABLE CalendarItem ("
            "ROWID INTEGER PRIMARY KEY, calendar_id INTEGER, summary TEXT, "
            "start_date REAL, end_date REAL, all_day INTEGER)"
        )
        cal_ids: dict[str, int] = {}
        for r in rows:
            title = r["calendar"]
            if title not in cal_ids:
                cal_ids[title] = len(cal_ids) + 1
                conn.execute(
                    "INSERT INTO Calendar (ROWID, title) VALUES (?, ?)",
                    (cal_ids[title], title),
                )
            conn.execute(
                "INSERT INTO CalendarItem (calendar_id, summary, start_date, end_date, all_day) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    cal_ids[title],
                    r["summary"],
                    _to_cocoa(r["start"]),
                    _to_cocoa(r["end"]),
                    int(r.get("all_day", 0)),
                ),
            )
        conn.commit()
    finally:
        conn.close()


class CalendarCollectorTests(unittest.TestCase):
    def _collect(self, home: Path, roles, **kwargs):
        return collect_calendar(
            kwargs.get("profiles", []),
            datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 1, 23, 59, tzinfo=timezone.utc),
            home,
            kwargs.get("classify", lambda _hay, _profiles: "X"),
            _make_event,
            calendar_roles=roles,
        )

    def test_no_selection_returns_empty_without_touching_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No DB written, no roles → must not raise and must be empty.
            self.assertEqual(self._collect(Path(tmp), {}), [])

    def test_collects_event_in_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_calendar_db(home, [{
                "calendar": "Work",
                "summary": "AXOR OneFlow",
                "start": datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc),
                "end": datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            }])
            out = self._collect(home, {"work": ROLE_SCHEDULED_CONTEXT})
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "Calendar")
            self.assertIn("AXOR OneFlow", out[0]["detail"])
            self.assertEqual(out[0]["calendar_role"], ROLE_SCHEDULED_CONTEXT)
            self.assertEqual(out[0]["timestamp"], datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc))

    def test_excludes_all_day_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_calendar_db(home, [{
                "calendar": "Work",
                "summary": "Vacation",
                "start": datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
                "end": datetime(2026, 4, 1, 23, 59, tzinfo=timezone.utc),
                "all_day": 1,
            }])
            self.assertEqual(self._collect(home, {"work": ROLE_SCHEDULED_CONTEXT}), [])

    def test_only_selected_calendars_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_calendar_db(home, [
                {"calendar": "Work", "summary": "Meeting",
                 "start": datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
                 "end": datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)},
                {"calendar": "Family", "summary": "Dinner",
                 "start": datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc),
                 "end": datetime(2026, 4, 1, 19, 0, tzinfo=timezone.utc)},
            ])
            out = self._collect(home, {"work": ROLE_SCHEDULED_CONTEXT})
            self.assertEqual([e["calendar_name"] for e in out], ["Work"])

    def test_role_per_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_calendar_db(home, [
                {"calendar": "TimeReport", "summary": "KidneySign",
                 "start": datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
                 "end": datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)},
            ])
            out = self._collect(home, {"timereport": ROLE_PRIMARY_CLAIM})
            self.assertEqual(out[0]["calendar_role"], ROLE_PRIMARY_CLAIM)

    def test_event_outside_window_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_calendar_db(home, [{
                "calendar": "Work", "summary": "Next day",
                "start": datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc),
                "end": datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
            }])
            self.assertEqual(self._collect(home, {"work": ROLE_SCHEDULED_CONTEXT}), [])

    def test_title_is_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_calendar_db(home, [{
                "calendar": "Work", "summary": "AXOR sync",
                "start": datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
                "end": datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            }])
            seen = {}

            def classify(hay, _profiles):
                seen["hay"] = hay
                return "financing-portal"

            out = self._collect(home, {"work": ROLE_SCHEDULED_CONTEXT}, classify=classify)
            self.assertEqual(out[0]["project"], "financing-portal")
            self.assertIn("AXOR sync", seen["hay"])

    def test_missing_db_raises_for_diagnosable_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                self._collect(Path(tmp), {"work": ROLE_SCHEDULED_CONTEXT})


class CalendarHelperTests(unittest.TestCase):
    def test_detect_missing_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, status = detect_calendar_db(Path(tmp))
            self.assertIsNone(path)
            self.assertEqual(status, "Calendar database not found")

    def test_parse_roles_with_explicit_roles(self):
        roles = parse_calendar_roles("TimeReport:primary_claim,Work:scheduled_context")
        self.assertEqual(roles["timereport"], ROLE_PRIMARY_CLAIM)
        self.assertEqual(roles["work"], ROLE_SCHEDULED_CONTEXT)

    def test_parse_roles_bare_name_defaults(self):
        roles = parse_calendar_roles("Work")
        self.assertEqual(roles["work"], DEFAULT_ROLE)

    def test_parse_roles_invalid_role_falls_back(self):
        roles = parse_calendar_roles("Work:bogus")
        self.assertEqual(roles["work"], DEFAULT_ROLE)

    def test_parse_roles_empty(self):
        self.assertEqual(parse_calendar_roles(None), {})
        self.assertEqual(parse_calendar_roles(""), {})


if __name__ == "__main__":
    unittest.main()
