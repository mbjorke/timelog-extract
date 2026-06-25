from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.cursor_agent_turns import collect_cursor_agent_turns
from collectors.cursor_composer import collect_cursor_composer_sessions


class CursorAgentTurnsTests(unittest.TestCase):
    def _write_composer_db(self, home: Path, composers: list[dict]) -> None:
        db_path = home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO ItemTable VALUES (?, ?)",
            ("composer.composerHeaders", json.dumps({"allComposers": composers})),
        )
        conn.commit()
        conn.close()

    def _write_structured_log(self, home: Path, workspace_id: str, lines: list[str]) -> None:
        log_dir = (
            home
            / "Library/Application Support/Cursor/logs/20260611T090000/window1_wb0/exthost/anysphere.cursor-always-local"
        )
        log_dir.mkdir(parents=True)
        name = f"Cursor Structured Logs.workspaceId-{workspace_id}.20260611T090008_test.log"
        (log_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_collect_cursor_agent_turns_emits_label_and_skips_composer_dup(self):
        cid = "92d11fea-5f15-403d-b3e0-0b9e5635ea5b"
        ws = "1807d04adc753be7ca72d645c0863c27"
        composers = [
            {
                "composerId": cid,
                "name": "Freelance bridge dashboard development",
                "createdAt": 1781158944337,
                "lastUpdatedAt": 1781158944337,
                "workspaceIdentifier": {
                    "uri": {"fsPath": "/Users/example/Workspace/Project/timelog-extract"},
                },
            }
        ]
        log_lines = [
            (
                '2026-06-11 09:10:00.000 [info] {"level":"info","key":"composer",'
                '"message":"agent.turn.start","metadata":{"conversation_id":"'
                + cid
                + '","request_id":"r1"}}'
            ),
            (
                '2026-06-11 09:40:00.000 [info] {"level":"info","key":"composer",'
                '"message":"agent.turn.start","metadata":{"conversation_id":"'
                + cid
                + '","request_id":"r2"}}'
            ),
        ]
        profiles = [
            {
                "name": "timelog-extract",
                "match_terms": ["timelog-extract", "mbjorke/timelog-extract"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(home, composers)
            self._write_structured_log(home, ws, log_lines)
            dt_from = datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc)
            local_tz = timezone.utc

            def make_event(source, ts, detail, project, anchors=None):
                return {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                    "anchors": anchors or {},
                }

            events, covered = collect_cursor_agent_turns(
                profiles, dt_from, dt_to, home, local_tz, lambda t, p: "timelog-extract", make_event
            )
            self.assertEqual(covered, {cid})
            self.assertGreaterEqual(len(events), 2)
            self.assertEqual(events[0]["source"], "Cursor (agent)")
            self.assertEqual(
                events[0]["anchors"].get("label"),
                "Freelance bridge dashboard development",
            )
            self.assertIn("turn", events[0]["detail"])
            self.assertNotIn("Freelance bridge", events[0]["detail"])
            composer_events = collect_cursor_composer_sessions(
                profiles,
                dt_from,
                dt_to,
                home,
                lambda t, p: "timelog-extract",
                make_event,
                exclude_composer_ids=covered,
            )
            self.assertEqual(composer_events, [])


if __name__ == "__main__":
    unittest.main()
