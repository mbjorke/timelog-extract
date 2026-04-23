from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.cursor import collect_cursor


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
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
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
                        "2026-04-22 09:00:00 [info] cursor_agent_exec.startup.workspace_paths "
                        "{\"workspacePathCount\":1} workspaceStorage/" + wid
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
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "Cursor")
            self.assertEqual(out[0]["project"], "Gittan CLI")

    def test_skips_cursor_git_status_heartbeat_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "c" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 16:32:19 [info] akturo: git_status: true, "
                        "/Users/me/Workspace/Project/akturo workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
            self.assertEqual(out, [])

    def test_lenient_profile_keeps_git_status_heartbeat_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "d" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 16:32:19 [info] akturo: git_status: true, "
                        "/Users/me/Workspace/Project/akturo workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                noise_profile="lenient",
            )
            self.assertEqual(len(out), 1)

    def test_ultra_strict_skips_vscode_diagnostics_executor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "e" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 17:25:46 [info] [VscodeDiagnosticsExecutor] EXECUTE: "
                        "/Users/me/Workspace/Project/akturo/src/index.vue workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                noise_profile="ultra-strict",
            )
            self.assertEqual(out, [])

    def test_strict_keeps_vscode_diagnostics_executor_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "f" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/akturo")
            self._write_log(
                home,
                "main/window.log",
                [
                    (
                        "2026-04-22 17:25:46 [info] [VscodeDiagnosticsExecutor] EXECUTE: "
                        "/Users/me/Workspace/Project/akturo/src/index.vue workspaceStorage/" + wid
                    )
                ],
            )
            out = collect_cursor(
                profiles=[],
                dt_from=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc),
                home=home,
                local_tz=timezone.utc,
                classify_project=lambda _hay, _profiles: "Akturo",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                noise_profile="strict",
            )
            self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
