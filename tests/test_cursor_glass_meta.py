from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.cursor_agent_turns import collect_cursor_agent_turns
from collectors.cursor_glass_meta import git_branch_leaf_at_path, load_glass_agent_tab_meta


class CursorGlassMetaTests(unittest.TestCase):
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

    @staticmethod
    def _git_init_with_branch(repo: Path, branch: str) -> None:
        """Create a repo on ``branch`` without requiring ``git init -b`` (older git)."""
        subprocess.run(
            ["git", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    def test_glass_tab_label_when_composer_header_missing(self):
        """GH-348: Glass PR tab label enriches Multitask chats missing headers."""
        cid = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        ws = "0507ce8a6b076915779412b4dd8bd6f9"
        # Neutral fixture paths (no expanded home segments in committed tests).
        repo_path = "/tmp/project-alpha"
        glass_payload = {
            "version": 2,
            "stableTabs": [],
            "workspaceTabs": [
                {
                    "id": "pr:example",
                    "kind": "pr",
                    "label": "Restore agent labels",
                    "props": {
                        "ownerAgentId": cid,
                        "branchName": "task/cursor-label-fallback-348",
                        "prTitle": "Restore agent labels",
                        "prUrl": "https://github.com/example/project-alpha/pull/1",
                        "repoPath": repo_path,
                    },
                }
            ],
        }
        payload = {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": cid,
            "session_id": cid,
            "workspace_roots": [repo_path],
            "prompt": "enrich missing composer headers",
        }
        body = (
            "[2026-07-09T19:00:00.000Z] Hook step requested: beforeSubmitPrompt\n"
            "INPUT:\n"
            + json.dumps(payload, indent=2)
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(
                home,
                [],
                extra_rows=[
                    (
                        f"cursor/glass.tabs.v2/{ws}/state.json",
                        json.dumps(glass_payload),
                    )
                ],
            )
            self._write_hooks_log(home, ws, body)
            events, covered = collect_cursor_agent_turns(
                [],
                datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc),
                home,
                timezone.utc,
                lambda t, p: "project-alpha",
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["anchors"].get("label"), "Restore agent labels")
            self.assertEqual(events[0]["anchors"].get("branch"), "cursor-label-fallback-348")
            self.assertIn("(@cursor-label-fallback-348)", events[0]["detail"])

    def test_glass_pr_number_label_rejected_keeps_branch(self):
        """GH-351: PR-shaped Glass tab labels must not become session titles."""
        cid = "dddddddd-eeee-ffff-0000-111111111111"
        ws = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        repo_path = "/tmp/project-alpha"
        glass_payload = {
            "version": 2,
            "stableTabs": [],
            "workspaceTabs": [
                {
                    "id": "pr:spike",
                    "kind": "pr",
                    "label": "PR #347: spike title",
                    "props": {
                        "ownerAgentId": cid,
                        "branchName": "task/work-unit-v2-spike-267",
                        "prTitle": "spike title",
                        "prUrl": "https://github.com/example/project-alpha/pull/347",
                        "repoPath": repo_path,
                    },
                }
            ],
        }
        payload = {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": cid,
            "session_id": cid,
            "workspace_roots": [repo_path],
            "prompt": "reject sticky PR tab title",
        }
        body = (
            "[2026-07-09T21:00:00.000Z] Hook step requested: beforeSubmitPrompt\n"
            "INPUT:\n"
            + json.dumps(payload, indent=2)
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(
                home,
                [],
                extra_rows=[
                    (
                        f"cursor/glass.tabs.v2/{ws}/state.json",
                        json.dumps(glass_payload),
                    )
                ],
            )
            self._write_hooks_log(home, ws, body)
            events, covered = collect_cursor_agent_turns(
                [],
                datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc),
                home,
                timezone.utc,
                lambda t, p: "project-alpha",
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertEqual(len(events), 1)
            label = events[0]["anchors"].get("label")
            self.assertNotEqual(label, "PR #347: spike title")
            self.assertFalse(str(label or "").upper().startswith("PR #"))
            # Dir leaf remains usable when the Glass title is rejected.
            self.assertEqual(label, "project-alpha")
            self.assertEqual(events[0]["anchors"].get("branch"), "work-unit-v2-spike-267")
            self.assertIn("(@work-unit-v2-spike-267)", events[0]["detail"])

    def test_glass_terminal_tab_label_ignored_falls_back_to_dir(self):
        """GH-361: Multitask terminal tab titles must not become session labels."""
        cid = "eeeeeeee-ffff-0000-1111-222222222222"
        ws = "b2c3d4e5f60718293a4b5c6d7e8f90a1"
        repo_path = "/tmp/project-alpha"
        glass_payload = {
            "version": 2,
            "stableTabs": [],
            "workspaceTabs": [
                {
                    "id": "terminal:example",
                    "kind": "terminal",
                    "label": "gittan-dev report --yesterday",
                    "props": {
                        "ownerAgentId": cid,
                        "repoPath": repo_path,
                    },
                }
            ],
        }
        payload = {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": cid,
            "session_id": cid,
            "workspace_roots": [repo_path],
            "prompt": "ignore terminal tab titles",
        }
        body = (
            "[2026-07-09T22:00:00.000Z] Hook step requested: beforeSubmitPrompt\n"
            "INPUT:\n"
            + json.dumps(payload, indent=2)
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(
                home,
                [],
                extra_rows=[
                    (
                        f"cursor/glass.tabs.v2/{ws}/state.json",
                        json.dumps(glass_payload),
                    )
                ],
            )
            self._write_hooks_log(home, ws, body)
            events, covered = collect_cursor_agent_turns(
                [],
                datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc),
                home,
                timezone.utc,
                lambda t, p: "project-alpha",
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertEqual(len(events), 1)
            label = events[0]["anchors"].get("label")
            self.assertNotEqual(label, "gittan-dev report --yesterday")
            # Dir leaf fallback, same convention as the GH-351 PR-title reject.
            self.assertEqual(label, "project-alpha")

    def test_glass_terminal_tab_skipped_valid_tab_label_wins(self):
        """GH-361: a non-terminal tab's label wins over a terminal tab's title."""
        cid = "ffffffff-0000-1111-2222-333333333333"
        ws = "c3d4e5f60718293a4b5c6d7e8f90a1b2"
        glass_payload = {
            "version": 2,
            "stableTabs": [],
            "workspaceTabs": [
                {
                    "id": "terminal:example",
                    "kind": "terminal",
                    "label": "zsh",
                    "props": {"ownerAgentId": cid},
                },
                {
                    "id": "pr:example",
                    "kind": "pr",
                    "label": "Fix terminal title leak",
                    "props": {
                        "ownerAgentId": cid,
                        "branchName": "task/361-glass-terminal-tab-label",
                    },
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(
                home,
                [],
                extra_rows=[
                    (
                        f"cursor/glass.tabs.v2/{ws}/state.json",
                        json.dumps(glass_payload),
                    )
                ],
            )
            meta = load_glass_agent_tab_meta(home)
            self.assertEqual(meta[cid].get("label"), "Fix terminal title leak")
            self.assertEqual(meta[cid].get("branch"), "361-glass-terminal-tab-label")

    def test_glass_only_terminal_tabs_yield_no_meta(self):
        """GH-361: agents whose only Glass tabs are terminals get no tab meta."""
        cid = "00000000-1111-2222-3333-444444444444"
        ws = "d4e5f60718293a4b5c6d7e8f90a1b2c3"
        glass_payload = {
            "version": 2,
            "stableTabs": [
                {
                    "id": "terminal:one",
                    "kind": "terminal",
                    "label": "bash",
                    "props": {"ownerAgentId": cid},
                }
            ],
            "workspaceTabs": [
                {
                    "id": "terminal:two",
                    "kind": "terminal",
                    "label": "gittan-dev report --yesterday",
                    "props": {"ownerAgentId": cid},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(
                home,
                [],
                extra_rows=[
                    (
                        f"cursor/glass.tabs.v2/{ws}/state.json",
                        json.dumps(glass_payload),
                    )
                ],
            )
            self.assertEqual(load_glass_agent_tab_meta(home), {})

    def test_glass_shell_title_label_rejected_keeps_branch(self):
        """GH-361: bare shell names are dropped even on non-terminal tabs."""
        cid = "11111111-2222-3333-4444-555555555555"
        ws = "e5f60718293a4b5c6d7e8f90a1b2c3d4"
        glass_payload = {
            "version": 2,
            "stableTabs": [],
            "workspaceTabs": [
                {
                    "id": "pr:example",
                    "kind": "pr",
                    "label": "zsh",
                    "props": {
                        "ownerAgentId": cid,
                        "branchName": "task/361-shell-title-guard",
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_composer_db(
                home,
                [],
                extra_rows=[
                    (
                        f"cursor/glass.tabs.v2/{ws}/state.json",
                        json.dumps(glass_payload),
                    )
                ],
            )
            meta = load_glass_agent_tab_meta(home)
            self.assertNotIn("label", meta.get(cid, {}))
            self.assertEqual(meta[cid].get("branch"), "361-shell-title-guard")

    def test_git_branch_fallback_when_composer_header_missing(self):
        """GH-348: workspace_roots HEAD branch when Glass/header have no branch."""
        cid = "cccccccc-dddd-eeee-ffff-000000000000"
        ws = "1807d04adc753be7ca72d645c0863c27"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            repo = home / "workspace" / "project-beta"
            repo.mkdir(parents=True)
            self._git_init_with_branch(repo, "task/display-gap-fix")
            payload = {
                "hook_event_name": "beforeSubmitPrompt",
                "conversation_id": cid,
                "session_id": cid,
                "workspace_roots": [str(repo)],
                "prompt": "add branch annotation",
            }
            body = (
                "[2026-07-09T20:00:00.000Z] Hook step requested: beforeSubmitPrompt\n"
                "INPUT:\n"
                + json.dumps(payload, indent=2)
                + "\n"
            )
            self._write_composer_db(home, [])
            self._write_hooks_log(home, ws, body)
            events, covered = collect_cursor_agent_turns(
                [],
                datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 23, 59, tzinfo=timezone.utc),
                home,
                timezone.utc,
                lambda t, p: "project-beta",
                self._make_event,
            )
            self.assertEqual(covered, {cid})
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["anchors"].get("dir"), "project-beta")
            self.assertEqual(events[0]["anchors"].get("branch"), "display-gap-fix")
            self.assertIn("(@display-gap-fix)", events[0]["detail"])

    def test_glass_meta_helpers_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(load_glass_agent_tab_meta(home), {})
            self.assertIsNone(git_branch_leaf_at_path(str(home / "missing")))
            not_a_repo = home / "not-a-repo"
            not_a_repo.mkdir()
            self.assertIsNone(git_branch_leaf_at_path(str(not_a_repo)))
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._git_init_with_branch(repo, "main")
            # Generic workflow branch rejected as anchor.
            self.assertIsNone(git_branch_leaf_at_path(str(repo)))
            # Subdirectory workspace_roots still resolve via git discovery.
            sub = repo / "collectors"
            sub.mkdir()
            subprocess.run(
                ["git", "branch", "-M", "task/subdir-workspace"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            self.assertEqual(git_branch_leaf_at_path(str(sub)), "subdir-workspace")


if __name__ == "__main__":
    unittest.main()
