"""Unit tests for collectors.zed_db (SQLite read path)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors import zed
from collectors import zed_db

UTC = timezone.utc


class ZedDbTests(unittest.TestCase):
    def test_parse_various_timestamps(self):
        """Parse various timestamp formats."""
        utc = timezone.utc

        ts = zed._parse_zed_timestamp(1712745605)
        self.assertIsNotNone(ts)

        ts = zed._parse_zed_timestamp(1712745605000)
        self.assertIsNotNone(ts)

        ts = zed._parse_zed_timestamp("2026-04-10T12:00:05+00:00")
        self.assertIsNotNone(ts)
        self.assertEqual(ts.astimezone(utc), datetime(2026, 4, 10, 12, 0, 5, tzinfo=utc))

        ts = zed._parse_zed_timestamp("2026-04-10T12:00:05Z")
        self.assertIsNotNone(ts)

        ts = zed._parse_zed_timestamp("2026-04-10T12:00:05")
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.tzinfo)
        self.assertEqual(ts.astimezone(utc), datetime(2026, 4, 10, 12, 0, 5, tzinfo=utc))

        self.assertIsNone(zed._parse_zed_timestamp(None))
        self.assertIsNone(zed._parse_zed_timestamp("invalid"))

    def test_parse_zed_message_entry_role_keyed(self):
        """Parse Zed message entries with role-keyed format."""
        result = zed._parse_zed_message_entry({"role": "user", "content": "Hello"})
        self.assertEqual(result, ("user", "Hello"))

        result = zed._parse_zed_message_entry({"User": {"content": [{"Text": "Hello from user"}]}})
        self.assertEqual(result, ("user", "Hello from user"))

        result = zed._parse_zed_message_entry(
            {"Agent": {"content": [{"Text": "Hello from assistant"}]}}
        )
        self.assertEqual(result, ("agent", "Hello from assistant"))

        self.assertIsNone(zed._parse_zed_message_entry("not a dict"))
        self.assertIsNone(zed._parse_zed_message_entry({}))

    def test_join_strategy_reads_aliased_created_at(self):
        """JOIN path must select the timestamp expression it filters on."""
        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=UTC)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "zed.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, timestamp INTEGER)")
            cursor.execute(
                """
                CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    created_at INTEGER,
                    content TEXT
                )
                """
            )
            ts = int(datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC).timestamp())
            cursor.execute("INSERT INTO threads (id, timestamp) VALUES (?, ?)", ("t1", ts))
            cursor.execute(
                "INSERT INTO messages (id, thread_id, created_at, content) VALUES (?, ?, ?, ?)",
                ("m1", "t1", ts, json.dumps({"role": "user", "content": "join path ok"})),
            )
            conn.commit()
            conn.close()

            schema = zed_db._inspect_db_schema(db_path)
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            messages = zed_db._query_messages_join_threads(
                conn,
                schema,
                ["messages"],
                ["threads"],
                dt_from,
                dt_to,
            )
            conn.close()
            self.assertEqual(len(messages), 1)
            self.assertIn("join path ok", messages[0].content)


if __name__ == "__main__":
    unittest.main()
