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
    def _write_composer_db(
        self,
        home: Path,
        composers: list[dict],
        *,
        extra_rows: list[tuple[str, str]] | None = None,
    ) -> None:
        db_path = home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO ItemTable VALUES (?, ?)",
            ("composer.composerHeaders", json.dumps({"allComposers": composers})),
        )
        for key, value in extra_rows or []:
            conn.execute("INSERT INTO ItemTable VALUES (?, ?)", (key, value))
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
        day_folder: str = "20260709T180000",
    ) -> Path:
        log_dir = (
            home
            / "Library/Application Support/Cursor/logs"
            / day_folder
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
            self.assertEqual(events[0]["detail"], "ship the hooks parser")
            self.assertEqual(events[1]["detail"], "and add short prompt previews like Zed")
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
            # Fixture path is not a real git repo → no fabricated branch.
            self.assertIsNone(events[0]["anchors"].get("branch"))

    def test_hooks_in_long_lived_session_folder_named_before_window(self):
        """Folder name = app launch time; entries may be days newer (GH-363).

        A Cursor process launched 2026-07-07 still appends today's hooks to
        logs/20260707T*/ — pruning by folder name must not drop those turns.
        """
        cid = "3f0f8a30-0000-4000-8000-00000000d363"
        ws = "1807d04adc753be7ca72d645c0863c27"
        payload = {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": cid,
            "session_id": cid,
            "workspace_roots": ["/Users/example/Workspace/Project/timelog-extract"],
            "prompt": "keep counting turns from long-lived sessions",
        }
        body = (
            "[2026-07-09T10:00:00.000Z] Hook step requested: beforeSubmitPrompt\n"
            "INPUT:\n"
            + json.dumps(payload, indent=2)
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(home, [])
            # Session folder launched two days before the report window.
            self._write_hooks_log(home, ws, body, day_folder="20260707T083000")
            events, covered = collect_cursor_agent_turns(
                [],
                datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc),
                home,
                timezone.utc,
                lambda t, p: "timelog-extract",
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["source"], "Cursor (agent)")
            self.assertEqual(
                events[0]["detail"], "keep counting turns from long-lived sessions"
            )

    def test_log_day_dirs_bounded_session_age_prune_future_folders(self):
        """Lower bound = session-age pad; upper bound = window end +1 (GH-363)."""
        from collectors.cursor_log_scan import iter_log_day_dirs

        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp)
            for name in (
                "20260401T090000",  # beyond the session-age pad — pruned
                "20260601T090000",  # within the session-age pad — kept
                "20260707T083000",  # 2 days before window — must be kept
                "20260710T090000",  # window end +1 pad — kept
                "20260712T090000",  # after the pad — pruned
                "not-a-day-folder",  # unknown layout — kept
            ):
                (logs_dir / name).mkdir()
            dirs = iter_log_day_dirs(
                logs_dir,
                datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc),
                timezone.utc,
            )
            names = {d.name for d in dirs}
            self.assertEqual(
                names,
                {
                    "20260601T090000",
                    "20260707T083000",
                    "20260710T090000",
                    "not-a-day-folder",
                },
            )

    def test_prompt_preview_is_capped_and_single_line(self):
        from collectors.cursor_agent_turns import _prompt_preview

        long = "word " * 40 + "\nsecret-line-two"
        preview = _prompt_preview(long)
        self.assertEqual(len(preview), 80)
        self.assertNotIn("\n", preview)
        self.assertNotIn("secret-line-two", preview)

    def test_iter_hooks_json_objects_handles_many_turns_and_brace_noise(self):
        """Offset-based parsing (perf fix) must match the original per-turn
        join semantics: correct object per INPUT block, brace-noisy tool
        output does not desync later turns, and a large turn count does not
        blow up (would time out under the old O(n*turns) re-join)."""
        from collectors.cursor_agent_turns import _iter_hooks_json_objects

        def _input_block(payload: dict) -> str:
            return "INPUT:\n" + json.dumps(payload, indent=2) + "\n\nOUTPUT:\n(empty)\n"

        lines: list[str] = []
        expected: list[tuple[str, int]] = []
        for turn in range(400):
            ts_line = f"[2026-07-09T16:{turn % 60:02d}:00.000Z] Hook step requested: beforeSubmitPrompt"
            lines.append(ts_line)
            lines.extend(
                _input_block(
                    {
                        "hook_event_name": "beforeSubmitPrompt",
                        "conversation_id": "cid",
                        "turn": turn,
                        "prompt": "ship it",
                    }
                ).splitlines()
            )
            expected.append((ts_line, turn))
            lines.append("[2026-07-09T16:00:30.000Z] Hook step requested: postToolUse")
            lines.extend(
                _input_block(
                    {
                        "hook_event_name": "postToolUse",
                        "conversation_id": "cid",
                        "tool_output": json.dumps({"output": 'nested {"a":1} {"b":2} end'}),
                    }
                ).splitlines()
            )

        results = list(_iter_hooks_json_objects(lines))
        turn_results = [
            (ts, obj["turn"]) for ts, obj in results if obj.get("hook_event_name") == "beforeSubmitPrompt"
        ]
        self.assertEqual(turn_results, expected)
        # postToolUse blocks (with embedded braces) must also survive intact.
        tool_results = [obj for _ts, obj in results if obj.get("hook_event_name") == "postToolUse"]
        self.assertEqual(len(tool_results), 400)


if __name__ == "__main__":
    unittest.main()
