from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.windsurf import collect_windsurf


def _make_event(source, ts, detail, project, context_dir=None):
    event = {"source": source, "timestamp": ts, "detail": detail, "project": project}
    if context_dir:
        event["context_dir"] = context_dir
    return event


class WindsurfCollectorTests(unittest.TestCase):
    def _base(self, home: Path, app: str = "Windsurf") -> Path:
        return home / "Library" / "Application Support" / app

    def _write_workspace(self, home: Path, wid: str, folder_path: str, app: str = "Windsurf") -> None:
        ws = self._base(home, app) / "User" / "workspaceStorage" / wid
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "workspace.json").write_text(
            json.dumps({"folder": f"file://{folder_path}"}), encoding="utf-8"
        )

    def _write_log(self, home: Path, rel: str, lines: list[str], app: str = "Windsurf") -> None:
        p = self._base(home, app) / "logs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _collect(self, home: Path, **kwargs):
        return collect_windsurf(
            profiles=[],
            dt_from=datetime(2026, 5, 28, 0, 0, tzinfo=timezone.utc),
            dt_to=datetime(2026, 5, 28, 23, 59, tzinfo=timezone.utc),
            home=home,
            local_tz=timezone.utc,
            classify_project=kwargs.get("classify", lambda _hay, _profiles: "X"),
            make_event=_make_event,
            noise_profile=kwargs.get("noise_profile", "strict"),
        )

    def test_returns_empty_when_no_logs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._collect(Path(tmp)), [])

    def test_keeps_window_load_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-28 09:00:00.000 [info] WindsurfWindowsMainManager: Window will load "
                    "/Users/me/Workspace/Project/timelog-extract"
                ],
            )
            out = self._collect(home, classify=lambda _h, _p: "Gittan CLI")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "Windsurf")
            self.assertEqual(out[0]["project"], "Gittan CLI")
            # Working-directory leaf is preserved (privacy-safe, no /Users/ prefix).
            self.assertEqual(out[0]["context_dir"], "timelog-extract")

    def test_maps_workspace_id_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "a" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/timelog-extract")
            self._write_log(
                home,
                "window1/renderer.log",
                [f"2026-05-28 09:05:00.000 [info] focus workspaceStorage/{wid}"],
            )
            out = self._collect(home, classify=lambda _h, _p: "Gittan CLI")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["project"], "Gittan CLI")

    def test_skips_acp_feature_flag_heartbeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/exthost/exthost.log",
                [
                    "2026-05-28 09:10:00.000 [info] acp feature flags (after context update): acp "
                    "/Users/me/Workspace/Project/timelog-extract"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_stderr_subprocess_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-28 09:11:00.000 [warning] [stderr] "
                    "/Users/me/Downloads/offert.md"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_git_revparse_enoent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/exthost/vscode.git/Git.log",
                [
                    "2026-05-28 09:12:00.000 [warning] [Git][revParse] Unable to read file: "
                    "ENOENT /Users/me/Workspace/Project/timelog-extract/.git/refs/heads/main"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_home_dotfile_paths(self):
        # Shell config / agent stores under ~/.* must never be project work.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    f"2026-05-28 09:13:00.000 [info] env {home}/.zshrc",
                    f"2026-05-28 09:13:01.000 [info] cascade {home}/.codeium/windsurf/brain",
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_app_support_internal_paths(self):
        # Paths under Windsurf's own app-support dir are IDE internals, not work.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            internal = self._base(home) / "User" / "settings.json"
            self._write_log(
                home,
                "main.log",
                [f"2026-05-28 09:13:30.000 [info] wrote settings {internal}"],
            )
            self.assertEqual(self._collect(home), [])

    def test_naive_iso_bracket_timestamp_defaults_to_local_tz(self):
        # Bracket ISO timestamps without an offset parse naive; the shared core
        # must default them to local_tz instead of raising on the window check.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "[2026-05-28T09:15:00] WindsurfWindowsMainManager: Window will load "
                    "/Users/me/Workspace/Project/timelog-extract"
                ],
            )
            out = self._collect(home, classify=lambda _h, _p: "Gittan CLI")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["timestamp"].tzinfo, timezone.utc)

    def test_scans_windsurf_next_base_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-28 09:14:00.000 [info] WindsurfWindowsMainManager: Window will load "
                    "/Users/me/Workspace/Project/blueberry"
                ],
                app="Windsurf - Next",
            )
            out = self._collect(home, classify=lambda _h, _p: "Blueberry")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["project"], "Blueberry")

    def test_lenient_profile_keeps_acp_heartbeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/exthost/exthost.log",
                [
                    "2026-05-28 09:10:00.000 [info] acp feature flags (after context update): acp "
                    "/Users/me/Workspace/Project/timelog-extract"
                ],
            )
            self.assertEqual(len(self._collect(home, noise_profile="lenient")), 1)


if __name__ == "__main__":
    unittest.main()
