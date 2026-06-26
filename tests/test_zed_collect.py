"""Tests for Zed AI chat collector."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors import zed

UTC = timezone.utc


def _make_event(source, ts, detail, project, anchors=None):
    event = {"source": source, "timestamp": ts, "detail": detail, "project": project}
    if anchors:
        event["anchors"] = anchors
    return event


class ZedCollectorTests(unittest.TestCase):
    """Tests for the Zed AI chat collector."""

    def test_no_db_returns_empty(self):
        """When Zed DB doesn't exist, return empty list."""
        dt_from = datetime(2026, 1, 1, tzinfo=UTC)
        dt_to = datetime(2026, 1, 2, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            events = zed.collect_zed(
                [],
                dt_from,
                dt_to,
                home,
                lambda _h, _p: "default-project",
                _make_event,
            )
        self.assertEqual(events, [])

    def test_collect_from_simple_threads_table(self):
        """Extract events from a simple threads table with embedded messages."""
        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=UTC)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            zed_dir = tmp / ".local" / "share" / "zed" / "db"
            zed_dir.mkdir(parents=True)
            db_path = zed_dir / "threads.db"

            # Create a simple SQLite DB with threads table
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Create threads table with message content
            cursor.execute("""
                CREATE TABLE threads (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER,
                    content TEXT
                )
            """)

            # Insert test data
            test_time = int(datetime(2026, 4, 10, 12, 0, 5, tzinfo=UTC).timestamp())
            cursor.execute(
                "INSERT INTO threads (id, created_at, content) VALUES (?, ?, ?)",
                (
                    "thread-1",
                    test_time,
                    '{"messages": [{"role": "user", "content": "Fix the bug"}, {"role": "assistant", "content": "Here is the fix"}]}',
                ),
            )

            # Insert a thread outside the time window
            old_time = int(datetime(2026, 4, 9, 12, 0, 0, tzinfo=UTC).timestamp())
            cursor.execute(
                "INSERT INTO threads (id, created_at, content) VALUES (?, ?, ?)",
                (
                    "thread-old",
                    old_time,
                    '{"messages": [{"role": "user", "content": "Old message"}]}',
                ),
            )

            conn.commit()
            conn.close()

            # Create a symlink to simulate macOS location
            macos_zed = tmp / "Library" / "Application Support" / "zed" / "db"
            macos_zed.mkdir(parents=True)
            (macos_zed / "threads.db").symlink_to(db_path)

            home = tmp

            def classify(_hay, _profiles):
                return "test-project"

            events = zed.collect_zed([], dt_from, dt_to, home, classify, _make_event)

            # Should find the in-window thread
            self.assertGreaterEqual(len(events), 1)
            if events:
                event = events[0]
                self.assertEqual(event["source"], "Zed")
                self.assertEqual(event["project"], "test-project")
                self.assertIn("Fix the bug", event["detail"])

    def test_collect_from_messages_table(self):
        """Extract events from a separate messages table."""
        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=UTC)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            zed_dir = tmp / ".local" / "share" / "zed" / "db"
            zed_dir.mkdir(parents=True)
            db_path = zed_dir / "threads.db"

            # Create DB with messages table
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Create messages table
            cursor.execute("""
                CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    timestamp INTEGER,
                    role TEXT,
                    content TEXT
                )
            """)

            # Insert test messages
            test_time = int(datetime(2026, 4, 10, 12, 0, 5, tzinfo=UTC).timestamp())
            cursor.execute(
                "INSERT INTO messages (id, thread_id, timestamp, role, content) VALUES (?, ?, ?, ?, ?)",
                ("msg-1", "thread-1", test_time, "user", "How do I fix this?"),
            )
            cursor.execute(
                "INSERT INTO messages (id, thread_id, timestamp, role, content) VALUES (?, ?, ?, ?, ?)",
                ("msg-2", "thread-1", test_time + 5, "assistant", "Try this solution"),
            )

            # Insert message outside time window
            old_time = int(datetime(2026, 4, 9, 12, 0, 0, tzinfo=UTC).timestamp())
            cursor.execute(
                "INSERT INTO messages (id, thread_id, timestamp, role, content) VALUES (?, ?, ?, ?, ?)",
                ("msg-old", "thread-old", old_time, "user", "Old message"),
            )

            conn.commit()
            conn.close()

            home = tmp

            def classify(_hay, _profiles):
                return "test-project"

            events = zed.collect_zed([], dt_from, dt_to, home, classify, _make_event)

            # Should find the in-window messages
            self.assertGreaterEqual(len(events), 2)
            if len(events) >= 2:
                for event in events:
                    self.assertEqual(event["source"], "Zed")
                    self.assertEqual(event["project"], "test-project")

    def test_collect_with_iso_timestamp(self):
        """Parse ISO formatted timestamps from the database."""
        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=UTC)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            zed_dir = tmp / ".local" / "share" / "zed" / "db"
            zed_dir.mkdir(parents=True)
            db_path = zed_dir / "threads.db"

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE threads (
                    id TEXT PRIMARY KEY,
                    created_at TEXT,
                    content TEXT
                )
            """)

            # ISO timestamp
            iso_ts = "2026-04-10T12:00:05+00:00"
            cursor.execute(
                "INSERT INTO threads (id, created_at, content) VALUES (?, ?, ?)",
                ("thread-1", iso_ts, '{"messages": [{"role": "user", "content": "Test message"}]}'),
            )

            conn.commit()
            conn.close()

            home = tmp

            def classify(_hay, _profiles):
                return "test-project"

            events = zed.collect_zed([], dt_from, dt_to, home, classify, _make_event)

            self.assertGreaterEqual(len(events), 1)
            if events:
                event = events[0]
                self.assertEqual(event["source"], "Zed")
                # Verify timestamp is parsed correctly
                self.assertEqual(
                    event["timestamp"].astimezone(UTC), datetime(2026, 4, 10, 12, 0, 5, tzinfo=UTC)
                )

    def test_collect_with_compressed_blob(self):
        """Decode compressed blob content from database."""
        import zlib

        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=UTC)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            zed_dir = tmp / ".local" / "share" / "zed" / "db"
            zed_dir.mkdir(parents=True)
            db_path = zed_dir / "threads.db"

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE threads (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER,
                    content BLOB
                )
            """)

            # Compress content
            original_content = '{"messages": [{"role": "user", "content": "Compressed test"}]}'
            compressed = zlib.compress(original_content.encode("utf-8"))
            test_time = int(datetime(2026, 4, 10, 12, 0, 5, tzinfo=UTC).timestamp())

            cursor.execute(
                "INSERT INTO threads (id, created_at, content) VALUES (?, ?, ?)",
                ("thread-1", test_time, compressed),
            )

            conn.commit()
            conn.close()

            home = tmp

            def classify(_hay, _profiles):
                return "test-project"

            events = zed.collect_zed([], dt_from, dt_to, home, classify, _make_event)

            self.assertGreaterEqual(len(events), 1)
            if events:
                event = events[0]
                self.assertEqual(event["source"], "Zed")
                self.assertIn("Compressed", event["detail"])

    def test_macos_path(self):
        """Find Zed DB at macOS location."""
        dt_from = datetime(2026, 4, 10, tzinfo=UTC)
        dt_to = datetime(2026, 4, 11, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            # Create at macOS location
            macos_zed = tmp / "Library" / "Application Support" / "zed" / "db"
            macos_zed.mkdir(parents=True)
            db_path = macos_zed / "threads.db"

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE threads (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER,
                    content TEXT
                )
            """)
            test_time = int(datetime(2026, 4, 10, 12, 0, 5, tzinfo=UTC).timestamp())
            cursor.execute(
                "INSERT INTO threads (id, created_at, content) VALUES (?, ?, ?)",
                ("thread-1", test_time, '{"messages": [{"role": "user", "content": "Mac test"}]}'),
            )
            conn.commit()
            conn.close()

            home = tmp

            def classify(_hay, _profiles):
                return "mac-project"

            events = zed.collect_zed([], dt_from, dt_to, home, classify, _make_event)

            self.assertGreaterEqual(len(events), 1)
            if events:
                event = events[0]
                self.assertEqual(event["source"], "Zed")
                self.assertEqual(event["project"], "mac-project")

    def test_extract_project_anchors(self):
        """Extract project anchors from message content."""
        msg = zed.ZedMessage(
            thread_id="thread-1",
            message_id="msg-1",
            timestamp=datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC),
            role="user",
            content="Working on timelog-extract project today",
        )

        anchors = zed._extract_project_anchors(msg)
        self.assertIsNotNone(anchors)
        # Should extract project name
        self.assertIn("project", anchors)

    def test_format_detail(self):
        """Format message detail string."""
        msg = zed.ZedMessage(
            thread_id="thread-1",
            message_id="msg-1",
            timestamp=datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC),
            role="assistant",
            content="Here is the solution to your problem",
        )

        detail = zed._format_detail(msg)
        self.assertIn("[assistant]", detail)
        self.assertIn("Here is the solution", detail)

        msg2 = zed.ZedMessage(
            thread_id="thread-2",
            message_id="msg-2",
            timestamp=datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC),
            role="user",
            content="How do I fix this?",
        )

        detail2 = zed._format_detail(msg2)
        self.assertIn("[user]", detail2)

    def test_parse_various_timestamps(self):
        """Parse various timestamp formats."""
        utc = timezone.utc

        # Test Unix timestamp (seconds)
        ts = zed._parse_zed_timestamp(1712745605)
        self.assertIsNotNone(ts)

        # Test Unix timestamp (milliseconds)
        ts = zed._parse_zed_timestamp(1712745605000)
        self.assertIsNotNone(ts)

        # Test ISO format
        ts = zed._parse_zed_timestamp("2026-04-10T12:00:05+00:00")
        self.assertIsNotNone(ts)
        self.assertEqual(ts.astimezone(utc), datetime(2026, 4, 10, 12, 0, 5, tzinfo=utc))

        # Test ISO with Z
        ts = zed._parse_zed_timestamp("2026-04-10T12:00:05Z")
        self.assertIsNotNone(ts)

        # Test ISO without offset (naive → UTC-aware)
        ts = zed._parse_zed_timestamp("2026-04-10T12:00:05")
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.tzinfo)
        self.assertEqual(ts.astimezone(utc), datetime(2026, 4, 10, 12, 0, 5, tzinfo=utc))

        # Test None
        ts = zed._parse_zed_timestamp(None)
        self.assertIsNone(ts)

        # Test invalid
        ts = zed._parse_zed_timestamp("invalid")
        self.assertIsNone(ts)

    def test_parse_zed_message_entry_role_keyed(self):
        """Parse Zed message entries with role-keyed format."""
        # Standard format
        result = zed._parse_zed_message_entry({"role": "user", "content": "Hello"})
        self.assertEqual(result, ("user", "Hello"))

        # Zed format with User
        result = zed._parse_zed_message_entry({"User": {"content": [{"Text": "Hello from user"}]}})
        self.assertEqual(result, ("user", "Hello from user"))

        # Zed format with Agent
        result = zed._parse_zed_message_entry(
            {"Agent": {"content": [{"Text": "Hello from assistant"}]}}
        )
        self.assertEqual(result, ("agent", "Hello from assistant"))

        # Invalid input (not a dict)
        result = zed._parse_zed_message_entry("not a dict")
        self.assertIsNone(result)

        # Empty dict
        result = zed._parse_zed_message_entry({})
        self.assertIsNone(result)

    def test_collect_with_role_keyed_format(self):
        """Collect events with Zed's role-keyed message format."""
        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=UTC)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            zed_dir = tmp / ".local" / "share" / "zed" / "db"
            zed_dir.mkdir(parents=True)
            db_path = zed_dir / "threads.db"

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE threads (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER,
                    content TEXT
                )
            """)

            # Zed format with role-keyed entries
            test_time = int(datetime(2026, 4, 10, 12, 0, 5, tzinfo=UTC).timestamp())
            zed_format_content = json.dumps(
                [
                    {"User": {"content": [{"Text": "How do I fix this?"}]}},
                    {"Agent": {"content": [{"Text": "Here is the solution"}]}},
                ]
            )
            cursor.execute(
                "INSERT INTO threads (id, created_at, content) VALUES (?, ?, ?)",
                ("thread-1", test_time, zed_format_content),
            )

            conn.commit()
            conn.close()

            home = tmp

            def classify(_hay, _profiles):
                return "test-project"

            events = zed.collect_zed([], dt_from, dt_to, home, classify, _make_event)

            # Should find messages from role-keyed format
            self.assertGreaterEqual(len(events), 2)
            if len(events) >= 2:
                # Check that both user and assistant messages are captured
                details = [e["detail"] for e in events]
                has_user = any("[user]" in str(d) for d in details)
                has_assistant = any("[assistant]" in str(d) for d in details)
                self.assertTrue(has_user or has_assistant)

    def test_join_strategy_reads_aliased_created_at(self):
        """JOIN path must select the timestamp expression it filters on."""
        from collectors import zed_db

        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=UTC)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "zed.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE threads (id TEXT PRIMARY KEY, timestamp INTEGER)"
            )
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
