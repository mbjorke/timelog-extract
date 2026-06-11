from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.domain import classify_project
from collectors.cursor_composer import collect_cursor_composer_sessions


class CursorComposerTests(unittest.TestCase):
    def test_collect_cursor_composer_sessions_emits_label_anchor(self):
        ts_ms = int(datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc).timestamp() * 1000)
        payload = {
            "allComposers": [
                {
                    "type": "head",
                    "composerId": "abc-123",
                    "name": "Freelance bridge dashboard development",
                    "lastUpdatedAt": ts_ms,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.vscdb"
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute(
                "INSERT INTO ItemTable VALUES (?, ?)",
                ("composer.composerHeaders", json.dumps(payload)),
            )
            conn.commit()
            conn.close()
            home = Path(tmp)
            cursor_dir = home / "Library/Application Support/Cursor/User/globalStorage"
            cursor_dir.mkdir(parents=True)
            (cursor_dir / "state.vscdb").write_bytes(db_path.read_bytes())

            dt_from = datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc)
            events = collect_cursor_composer_sessions(
                profiles=[],
                dt_from=dt_from,
                dt_to=dt_to,
                home=home,
                classify_project=lambda text, profiles: "Uncategorized",
                make_event=lambda source, ts, detail, project, anchors=None: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                    "anchors": anchors or {},
                },
            )
        self.assertEqual(len(events), 1)
        self.assertIn("freelance bridge", events[0]["anchors"].get("label", ""))
        self.assertIn("Freelance bridge", events[0]["detail"])

    def test_collect_cursor_composer_sessions_emits_span_heartbeats(self):
        created_ms = int(datetime(2026, 6, 11, 9, 22, tzinfo=timezone.utc).timestamp() * 1000)
        updated_ms = int(datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc).timestamp() * 1000)
        payload = {
            "allComposers": [
                {
                    "composerId": "abc-123",
                    "name": "Freelance bridge dashboard development",
                    "createdAt": created_ms,
                    "lastUpdatedAt": updated_ms,
                    "workspaceIdentifier": {
                        "uri": {
                            "fsPath": "/Users/example/Workspace/Project/timelog-extract",
                        }
                    },
                }
            ]
        }
        profiles = [
            {
                "name": "timelog-extract",
                "match_terms": ["timelog-extract", "mbjorke/timelog-extract"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.vscdb"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute(
                "INSERT INTO ItemTable VALUES (?, ?)",
                ("composer.composerHeaders", json.dumps(payload)),
            )
            conn.commit()
            conn.close()
            home = Path(tmp)
            cursor_dir = home / "Library/Application Support/Cursor/User/globalStorage"
            cursor_dir.mkdir(parents=True)
            (cursor_dir / "state.vscdb").write_bytes(db_path.read_bytes())

            events = collect_cursor_composer_sessions(
                profiles=profiles,
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=lambda text, p: classify_project(text, p, "Uncategorized"),
                make_event=lambda source, ts, detail, project, anchors=None: {
                    "source": source,
                    "timestamp": ts,
                    "local_ts": ts,
                    "detail": detail,
                    "project": project,
                    "anchors": anchors or {},
                },
            )
        self.assertGreaterEqual(len(events), 8)
        self.assertTrue(all(event["project"] == "timelog-extract" for event in events))
        from core.domain import compute_sessions, session_duration_hours
        from core.sources import AI_SOURCES

        sessions = compute_sessions(events, gap_minutes=15)
        self.assertEqual(len(sessions), 1)
        start_ts, end_ts, session_events = sessions[0]
        hours = session_duration_hours(
            session_events,
            start_ts,
            end_ts,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            ai_sources=AI_SOURCES,
        )
        self.assertGreaterEqual(hours, 1.5)

    def test_stale_revived_composer_emits_point_event_only(self):
        created_ms = int(datetime(2026, 5, 28, 11, 35, tzinfo=timezone.utc).timestamp() * 1000)
        updated_ms = int(datetime(2026, 6, 11, 11, 31, tzinfo=timezone.utc).timestamp() * 1000)
        payload = {
            "allComposers": [
                {
                    "composerId": "stale-1",
                    "name": "Supabase åtkomst för Lovable",
                    "createdAt": created_ms,
                    "lastUpdatedAt": updated_ms,
                    "workspaceIdentifier": {
                        "uri": {"fsPath": "/Users/example/Workspace/financing-portal"},
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.vscdb"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute(
                "INSERT INTO ItemTable VALUES (?, ?)",
                ("composer.composerHeaders", json.dumps(payload)),
            )
            conn.commit()
            conn.close()
            home = Path(tmp)
            cursor_dir = home / "Library/Application Support/Cursor/User/globalStorage"
            cursor_dir.mkdir(parents=True)
            (cursor_dir / "state.vscdb").write_bytes(db_path.read_bytes())

            events = collect_cursor_composer_sessions(
                profiles=[],
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=lambda text, profiles: "Uncategorized",
                make_event=lambda source, ts, detail, project, anchors=None: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                    "anchors": anchors or {},
                },
            )
        self.assertEqual(len(events), 1)

    def test_composer_outside_report_window_is_excluded(self):
        created_ms = int(datetime(2026, 5, 28, 11, 35, tzinfo=timezone.utc).timestamp() * 1000)
        updated_ms = int(datetime(2026, 6, 11, 11, 31, tzinfo=timezone.utc).timestamp() * 1000)
        payload = {
            "allComposers": [
                {
                    "composerId": "future-1",
                    "name": "Future composer",
                    "createdAt": created_ms,
                    "lastUpdatedAt": updated_ms,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.vscdb"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute(
                "INSERT INTO ItemTable VALUES (?, ?)",
                ("composer.composerHeaders", json.dumps(payload)),
            )
            conn.commit()
            conn.close()
            home = Path(tmp)
            cursor_dir = home / "Library/Application Support/Cursor/User/globalStorage"
            cursor_dir.mkdir(parents=True)
            (cursor_dir / "state.vscdb").write_bytes(db_path.read_bytes())

            events = collect_cursor_composer_sessions(
                profiles=[],
                dt_from=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2024, 1, 2, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=lambda text, profiles: "Uncategorized",
                make_event=lambda source, ts, detail, project, anchors=None: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                    "anchors": anchors or {},
                },
            )
        self.assertEqual(events, [])

    def test_collect_cursor_composer_sessions_classifies_from_workspace_path(self):
        ts_ms = int(datetime(2026, 6, 11, 11, 58, tzinfo=timezone.utc).timestamp() * 1000)
        payload = {
            "allComposers": [
                {
                    "composerId": "abc-123",
                    "name": "Freelance bridge dashboard development",
                    "lastUpdatedAt": ts_ms,
                    "workspaceIdentifier": {
                        "uri": {
                            "fsPath": "/Users/example/Workspace/Project/timelog-extract",
                        }
                    },
                    "trackedGitRepos": [
                        {
                            "repoPath": "/Users/example/Workspace/Project/timelog-extract",
                            "branches": [
                                {
                                    "branchName": "claude/freelance-bridge-dashboard-CeFO5",
                                    "lastInteractionAt": ts_ms,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        profiles = [
            {
                "name": "timelog-extract",
                "match_terms": ["timelog-extract", "mbjorke/timelog-extract"],
                "tracked_urls": [],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.vscdb"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute(
                "INSERT INTO ItemTable VALUES (?, ?)",
                ("composer.composerHeaders", json.dumps(payload)),
            )
            conn.commit()
            conn.close()
            home = Path(tmp)
            cursor_dir = home / "Library/Application Support/Cursor/User/globalStorage"
            cursor_dir.mkdir(parents=True)
            (cursor_dir / "state.vscdb").write_bytes(db_path.read_bytes())

            events = collect_cursor_composer_sessions(
                profiles=profiles,
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=lambda text, p: classify_project(text, p, "Uncategorized"),
                make_event=lambda source, ts, detail, project, anchors=None: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                    "anchors": anchors or {},
                },
            )
        self.assertEqual(events[0]["project"], "timelog-extract")
        self.assertEqual(events[0]["anchors"].get("dir"), "timelog-extract")


if __name__ == "__main__":
    unittest.main()
