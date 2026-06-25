from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.cursor import collect_cursor
from tests.event_helpers import make_test_event


class CursorNoiseFilterTests(unittest.TestCase):
    def _write_workspace(self, home: Path, wid: str, folder_path: str) -> None:
        ws = (
            home
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "workspaceStorage"
            / wid
        )
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "workspace.json").write_text(
            json.dumps({"folder": f"file://{folder_path}"}),
            encoding="utf-8",
        )

    def _write_log(self, home: Path, rel: str, lines: list[str]) -> None:
        p = home / "Library" / "Application Support" / "Cursor" / "logs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_skips_cursor_diagnostic_noise_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "a" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/ass-membra")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 08:14:12 [error] Error getting submodules: "
                        "A system error occurred (ENOENT: ... workspaceStorage/" + wid + ")"
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "X",
                make_event=make_test_event,
            )
            self.assertEqual(out, [])

    def test_keeps_non_noise_cursor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "b" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/timelog-extract")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 09:00:00 [info] user saved src/api.ts "
                        "workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Gittan CLI",
                make_event=make_test_event,
            )
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "Cursor")
            self.assertEqual(out[0]["project"], "Gittan CLI")

    def test_cursor_event_carries_workspace_leaf_context_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "c" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/timelog-extract")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 09:00:00 [info] editing src/api.ts "
                        "workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "X",
                make_event=make_test_event,
            )
            self.assertEqual(len(out), 1)
            # Privacy-safe leaf only — no /Users/<name>/ prefix.
            self.assertEqual(out[0]["anchors"]["dir"], "timelog-extract")

    def test_skips_cursor_git_status_heartbeat_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "c" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 16:32:19 [info] project-alpha: git_status: true, "
                        "/Users/me/Workspace/Project/project-alpha workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Project Alpha",
                make_event=make_test_event,
            )
            self.assertEqual(out, [])

    def test_lenient_profile_also_skips_git_status_heartbeat_lines(self):
        """Machine pollers fire every ~3 min per open workspace even when idle —
        they fabricate hours and are dropped at every profile, including lenient."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "d" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 16:32:19 [info] project-alpha: git_status: true, "
                        "/Users/me/Workspace/Project/project-alpha workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Project Alpha",
                make_event=make_test_event,
                noise_profile="lenient",
            )
            self.assertEqual(out, [])

    def test_skips_extension_host_script_runner_and_marketplace_lines(self):
        """Statusline/hook script polling and marketplace cache refresh are IDE
        plumbing that fires constantly — dropped at every profile."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "a1" * 16
            self._write_workspace(home, wid, "/Users/me/.claude")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 19:56:52 [info] [2026-04-22T16:56:52.481Z] "
                        "Running script in directory: /Users/me/.claude workspaceStorage/" + wid
                    ),
                    (
                        "2026-04-22 20:31:31 [info] [2026-04-22T17:31:31.008Z] "
                        "[info] loadFromMarketplaceSource workspaceStorage/" + wid
                    ),
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Uncategorized",
                make_event=make_test_event,
                noise_profile="lenient",
            )
            self.assertEqual(out, [])

    def test_ultra_strict_skips_vscode_diagnostics_executor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "e" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 17:25:46 [info] [VscodeDiagnosticsExecutor] EXECUTE: "
                        "/Users/me/Workspace/Project/project-alpha/src/index.vue workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Project Alpha",
                make_event=make_test_event,
                noise_profile="ultra-strict",
            )
            self.assertEqual(out, [])

    def test_strict_skips_vscode_diagnostics_executor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "f" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 17:25:46 [info] [VscodeDiagnosticsExecutor] EXECUTE: "
                        "/Users/me/Workspace/Project/project-alpha/src/index.vue workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Project Alpha",
                make_event=make_test_event,
                noise_profile="strict",
            )
            self.assertEqual(out, [])

    def test_strict_skips_hooks_and_git_churn(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "9" * 32
            self._write_workspace(home, wid, "/Users/me/ax-finans")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 07:08:18 [info] Project config path (ax-finans): "
                        "/Users/me/ax-finans/.cursor/hooks.json workspaceStorage/" + wid
                    ),
                    (
                        "2026-04-22 07:08:22 [info] > git --git-dir /Users/me/ax-finans/.git status "
                        "workspaceStorage/" + wid
                    ),
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "financing-portal",
                make_event=make_test_event,
            )
            self.assertEqual(out, [])

    def test_skips_mcp_browser_click_error_lines(self):
        """cursor-ide-browser MCP write failures are IDE plumbing, not user work."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "4" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/customer-faq")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-06-19 05:58:00 [error] customer-faq browser_click.json — [error] "
                        '{"key":"mcp","message":"Error writing server response"} '
                        "workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 6, 19, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 19, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "customer-faq",
                make_event=make_test_event,
                noise_profile="lenient",
            )
            self.assertEqual(out, [])

    def test_skips_cursor_agent_worker_and_repository_tracker_heartbeats(self):
        """Agent-worker and RepositoryTracker poll on timers while Cursor is open."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "3" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/timelog-extract")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-06-23 00:11:23.299 [info] [cursor-agent-worker] Workspace roots: "
                        "/Users/me/Workspace/Project/timelog-extract workspaceStorage/" + wid
                    ),
                    (
                        "2026-06-22 11:01:10.417 [info] [RepositoryTracker] Stored "
                        "repository path: github.com/ax-f /Users/me/ax-finans workspaceStorage/" + wid
                    ),
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 6, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 23, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "timelog-extract",
                make_event=make_test_event,
                noise_profile="lenient",
            )
            self.assertEqual(out, [])

    def test_skips_gittan_sync_artifact_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "1" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/timelog-extract")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-05-01 11:18:02 [error] upload sync failed "
                        "/Users/me/.gittan-task/projects-config-trimming/timelog_projects.json "
                        "decisions-2026-05-01.json workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 5, 1, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "timelog-extract",
                make_event=make_test_event,
            )
            self.assertEqual(out, [])

    def test_skips_skills_cursor_sync_manifest_poller(self):
        """skills-cursor manifest sync fires on a timer while Cursor is open — not user work."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "2" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/project-alpha")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-06-15 02:17:30.381 [warning] Failed to persist sync manifest "
                        '{"skillDir":"/Users/me/.cursor/skills-cursor"} '
                        "workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 15, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Uncategorized",
                make_event=make_test_event,
                noise_profile="lenient",
            )
            self.assertEqual(out, [])

    def test_collect_cursor_reads_composer_without_logs_dir(self):
        import sqlite3

        payload = {
            "allComposers": [
                {
                    "composerId": "composer-only-1",
                    "name": "Project alpha feature work",
                    "createdAt": int(
                        datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc).timestamp() * 1000
                    ),
                    "lastUpdatedAt": int(
                        datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc).timestamp() * 1000
                    ),
                    "workspaceIdentifier": {
                        "uri": {"fsPath": "/Users/example/code/project-alpha"}
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db_dir = home / "Library/Application Support/Cursor/User/globalStorage"
            db_dir.mkdir(parents=True)
            conn = sqlite3.connect(db_dir / "state.vscdb")
            conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute(
                "INSERT INTO ItemTable VALUES (?, ?)",
                ("composer.composerHeaders", json.dumps(payload)),
            )
            conn.commit()
            conn.close()
            out = collect_cursor(
                profiles=[{"name": "project-alpha", "match_terms": ["project-alpha"]}],
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda hay, profiles: (
                    "project-alpha" if "project-alpha" in hay else "Uncategorized"
                ),
                make_event=make_test_event,
            )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["project"], "project-alpha")


if __name__ == "__main__":
    unittest.main()
