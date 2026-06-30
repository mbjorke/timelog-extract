"""Tests for the Conductor session collector."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.conductor import (
    _find_conductor_db,
    _message_text,
    _read_messages,
    _repo_slug,
    collect_conductor,
)

DT_FROM = datetime(2026, 6, 29, 0, 0, tzinfo=timezone.utc)
DT_TO = datetime(2026, 6, 29, 23, 59, tzinfo=timezone.utc)


def _classify_project(text, _profiles):
    return "timelog-extract" if "timelog-extract" in (text or "") else "Uncategorized"


def _make_event(source, ts, detail, project, anchors=None):
    return {
        "source": source,
        "timestamp": ts,
        "detail": detail,
        "project": project,
        "anchors": anchors,
    }


def _assistant_envelope(text: str) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-8",
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        }
    )


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE repos (id TEXT PRIMARY KEY, name TEXT, remote_url TEXT);
        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY, directory_name TEXT, branch TEXT, repository_id TEXT
        );
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, title TEXT, agent_type TEXT, workspace_id TEXT
        );
        CREATE TABLE session_messages (
            id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
            sent_at TEXT, created_at TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO repos VALUES (?,?,?)",
        ("r1", "timelog-extract", "https://github.com/mbjorke/timelog-extract.git"),
    )
    conn.execute(
        "INSERT INTO workspaces VALUES (?,?,?,?)",
        ("w1", "kolkata", "conductor-session-tid", "r1"),
    )
    conn.execute(
        "INSERT INTO sessions VALUES (?,?,?,?)",
        ("s1", "Analyze transcript", "claude", "w1"),
    )
    rows = [
        # readable user prompt — in window
        ("m1", "s1", "user", "hur går det med conductor som källa?",
         "2026-06-29T10:30:00.000Z", "2026-06-29T10:30:00.000Z"),
        # assistant text envelope — in window
        ("m2", "s1", "assistant", _assistant_envelope("Kort svar: tiden hittar in."),
         "2026-06-29T10:31:00.000Z", "2026-06-29T10:31:00.000Z"),
        # assistant noise (no text block) — dropped
        ("m3", "s1", "assistant",
         json.dumps({"type": "system", "subtype": "thinking_tokens"}),
         "2026-06-29T10:32:00.000Z", "2026-06-29T10:32:00.000Z"),
        # blank — dropped
        ("m4", "s1", "user", "   ",
         "2026-06-29T10:33:00.000Z", "2026-06-29T10:33:00.000Z"),
        # outside window — dropped
        ("m5", "s1", "user", "yesterday",
         "2026-06-28T10:30:00.000Z", "2026-06-28T10:30:00.000Z"),
    ]
    conn.executemany("INSERT INTO session_messages VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


class ConductorCollectTest(unittest.TestCase):
    def test_emits_readable_messages_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "conductor.db"
            _build_db(db)
            with _patched_db(db):
                events = collect_conductor(
                    [], DT_FROM, DT_TO, Path(tmp), _classify_project, _make_event
                )
        # m1 (user) + m2 (assistant text); noise/blank/out-of-window dropped.
        self.assertEqual(len(events), 2)
        self.assertTrue(all(e["source"] == "Conductor" for e in events))

    def test_attribution_and_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "conductor.db"
            _build_db(db)
            with _patched_db(db):
                events = collect_conductor(
                    [], DT_FROM, DT_TO, Path(tmp), _classify_project, _make_event
                )
        user_event = next(e for e in events if "[user]" in e["detail"])
        # Session name surfaces in the detail, project resolves from the repo row.
        self.assertIn("Analyze transcript", user_event["detail"])
        self.assertIn("hur går det med conductor", user_event["detail"])
        self.assertEqual(user_event["project"], "timelog-extract")
        self.assertEqual(user_event["anchors"], {"repo": "mbjorke/timelog-extract"})
        self.assertEqual(user_event["timestamp"].tzinfo, timezone.utc)

    def test_missing_database_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(_find_conductor_db(Path(tmp)))
            events = collect_conductor(
                [], DT_FROM, DT_TO, Path(tmp), _classify_project, _make_event
            )
            self.assertEqual(events, [])

    def test_repo_slug(self):
        self.assertEqual(
            _repo_slug("https://github.com/mbjorke/timelog-extract.git"),
            "mbjorke/timelog-extract",
        )
        self.assertEqual(
            _repo_slug("git@github.com:mbjorke/timelog-extract.git"),
            "mbjorke/timelog-extract",
        )
        self.assertIsNone(_repo_slug(None))
        self.assertIsNone(
            _repo_slug("https://gitlab.com/acme/widget.git"),
        )

    def test_corrupt_database_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "conductor.db"
            db.write_text("not sqlite", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Conductor database query failed"):
                _read_messages(db, DT_FROM, DT_TO)

    def test_schema_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "conductor.db"
            conn = sqlite3.connect(str(db))
            conn.execute("CREATE TABLE only_other (id INTEGER)")
            conn.commit()
            conn.close()
            with self.assertRaisesRegex(RuntimeError, "Conductor database query failed"):
                _read_messages(db, DT_FROM, DT_TO)

    def test_message_text_parsing(self):
        self.assertEqual(_message_text("user", "plain prompt"), "plain prompt")
        self.assertEqual(
            _message_text("assistant", _assistant_envelope("hello")), "hello"
        )
        self.assertIsNone(_message_text("assistant", '{"type":"system"}'))
        self.assertIsNone(_message_text("assistant", "not json"))
        self.assertIsNone(_message_text("user", "   "))


class _patched_db:
    """Point _find_conductor_db at a fixture database for the duration."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def __enter__(self):
        import collectors.conductor as mod

        self._orig = mod._CONDUCTOR_DB_PATHS
        mod._CONDUCTOR_DB_PATHS = [str(self.db_path)]
        return self

    def __exit__(self, *exc):
        import collectors.conductor as mod

        mod._CONDUCTOR_DB_PATHS = self._orig
        return False


if __name__ == "__main__":
    unittest.main()
