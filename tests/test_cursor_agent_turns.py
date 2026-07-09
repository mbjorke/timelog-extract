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
        log_dir.mkdir(parents=True, exist_ok=True)
        name = f"Cursor Structured Logs.workspaceId-{workspace_id}.20260611T090008_test.log"
        (log_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_hooks_log(
        self,
        home: Path,
        workspace_id: str,
        body: str,
        *,
        window: str = "window1_wb0",
        output: str = "output_20260709T190000",
    ) -> Path:
        log_dir = (
            home
            / "Library/Application Support/Cursor/logs/20260709T180000"
            / window
            / output
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"cursor.hooks.workspaceId-{workspace_id}.log"
        path.write_text(body, encoding="utf-8")
        return path

    @staticmethod
    def _make_event(source, ts, detail, project, anchors=None):
        return {
            "source": source,
            "timestamp": ts,
            "detail": detail,
            "project": project,
            "anchors": anchors or {},
        }

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

            events, covered = collect_cursor_agent_turns(
                profiles,
                dt_from,
                dt_to,
                home,
                local_tz,
                lambda t, p: "timelog-extract",
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertGreaterEqual(len(events), 2)
            self.assertEqual(events[0]["source"], "Cursor (agent)")
            self.assertEqual(
                events[0]["anchors"].get("label"),
                "Freelance bridge dashboard development",
            )
            # always-local path has no prompt text — keep turn-count detail.
            self.assertIn("turn", events[0]["detail"])
            self.assertNotIn("Freelance bridge", events[0]["detail"])
            composer_events = collect_cursor_composer_sessions(
                profiles,
                dt_from,
                dt_to,
                home,
                lambda t, p: "timelog-extract",
                self._make_event,
                exclude_composer_ids=covered,
            )
            self.assertEqual(composer_events, [])

    def test_hooks_before_submit_prompt_emits_turns_on_cursor_310(self):
        """Cursor 3.10+ moved turn starts into cursor.hooks (GH-345)."""
        cid = "f87253ed-0619-4e9d-ba0f-3005d58c9310"
        ws = "1807d04adc753be7ca72d645c0863c27"
        composers = [
            {
                "composerId": cid,
                "name": "Cursor 3.10 hooks turns",
                "createdAt": 1783615800000,
                "lastUpdatedAt": 1783620000000,
                "workspaceIdentifier": {
                    "uri": {"fsPath": "/Users/example/Workspace/Project/timelog-extract"},
                },
            }
        ]
        prompt_payload = {
            "hook_event_name": "beforeSubmitPrompt",
            "cursor_version": "3.10.20",
            "session_id": cid,
            "conversation_id": cid,
            "workspace_roots": ["/Users/example/Workspace/Project/timelog-extract"],
            "transcript_path": f"/Users/example/.cursor/projects/x/agent-transcripts/{cid}/{cid}.jsonl",
            "prompt": "ship the hooks parser",
        }
        later_payload = {
            **prompt_payload,
            "prompt": "and add short prompt previews like Zed",
        }

        def _input_block(payload: dict) -> str:
            return (
                "INPUT:\n"
                + json.dumps(payload, indent=2)
                + "\n\nOUTPUT:\n(empty)\n"
            )

        # tool_output embeds JSON braces — must not desync the INPUT parser.
        noisy_tool = {
            "hook_event_name": "postToolUse",
            "conversation_id": cid,
            "session_id": cid,
            "workspace_roots": ["/Users/example/Workspace/Project/timelog-extract"],
            "tool_name": "Shell",
            "tool_output": json.dumps({"output": 'nested {"a":1} {"b":2} end', "exitCode": 0}),
        }
        # Two window copies of the same turn — must not double-count.
        body = (
            "[2026-07-09T16:50:06.000Z] Hook step requested: beforeSubmitPrompt\n"
            + _input_block(prompt_payload)
            + "[2026-07-09T16:51:00.000Z] Hook step requested: postToolUse\n"
            + _input_block(noisy_tool)
            + "[2026-07-09T17:05:00.000Z] Hook step requested: beforeSubmitPrompt\n"
            + _input_block(later_payload)
            + "[2026-07-09T17:06:00.000Z] Hook step requested: preToolUse\n"
            + _input_block(
                {
                    "hook_event_name": "preToolUse",
                    "conversation_id": cid,
                    "session_id": cid,
                    "workspace_roots": ["/Users/example/Workspace/Project/timelog-extract"],
                    "tool_name": "Shell",
                }
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(home, composers)
            self._write_hooks_log(home, ws, body, window="window1_wb1")
            self._write_hooks_log(home, ws, body, window="window1_wb2", output="output_20260709T192412")
            dt_from = datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc)

            events, covered = collect_cursor_agent_turns(
                [],
                dt_from,
                dt_to,
                home,
                timezone.utc,
                lambda t, p: "timelog-extract",
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["source"], "Cursor (agent)")
            self.assertEqual(events[0]["anchors"].get("label"), "Cursor 3.10 hooks turns")
            self.assertEqual(events[0]["project"], "timelog-extract")
            self.assertEqual(events[0]["detail"], "[user] ship the hooks parser")
            self.assertEqual(events[1]["detail"], "[user] and add short prompt previews like Zed")
            hours = {e["timestamp"].hour for e in events}
            self.assertEqual(hours, {16, 17})

    def test_hooks_workspace_roots_classify_without_composer_header(self):
        cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        ws = "0507ce8a6b076915779412b4dd8bd6f9"
        payload = {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": cid,
            "session_id": cid,
            "workspace_roots": ["/Users/example/Workspace/Project/timelog-extract"],
            # Empty prompt → turn-count detail fallback.
            "prompt": "",
        }
        body = (
            "[2026-07-09T18:00:00.000Z] Hook step requested: beforeSubmitPrompt\n"
            "INPUT:\n"
            + json.dumps(payload, indent=2)
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(home, [])
            self._write_hooks_log(home, ws, body)
            events, covered = collect_cursor_agent_turns(
                [],
                datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc),
                home,
                timezone.utc,
                lambda t, p: "timelog-extract" if "timelog-extract" in (t or "") else None,
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["anchors"].get("dir"), "timelog-extract")
            self.assertEqual(events[0]["project"], "timelog-extract")
            # No prompt in payload → fall back to turn count.
            self.assertIn("turn", events[0]["detail"])

    def test_prompt_preview_is_capped_and_single_line(self):
        from collectors.cursor_agent_turns import _prompt_preview

        long = "word " * 40 + "\nsecret-line-two"
        preview = _prompt_preview(long)
        self.assertEqual(len(preview), 80)
        self.assertNotIn("\n", preview)
        self.assertNotIn("secret-line-two", preview)


if __name__ == "__main__":
    unittest.main()
