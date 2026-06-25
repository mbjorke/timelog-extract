from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.antigravity import collect_antigravity
from tests.event_helpers import make_test_event


class AntigravityCollectorTests(unittest.TestCase):
    def _base(self, home: Path) -> Path:
        return home / "Library" / "Application Support" / "Antigravity IDE"

    def _write_workspace(self, home: Path, wid: str, folder_path: str) -> None:
        ws = self._base(home) / "User" / "workspaceStorage" / wid
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "workspace.json").write_text(
            json.dumps({"folder": f"file://{folder_path}"}),
            encoding="utf-8",
        )

    def _write_log(self, home: Path, rel: str, lines: list[str]) -> None:
        p = self._base(home) / "logs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _collect(self, home: Path, **kwargs):
        return collect_antigravity(
            profiles=[],
            dt_from=datetime(2026, 5, 29, 0, 0, tzinfo=timezone.utc),
            dt_to=datetime(2026, 5, 29, 23, 59, tzinfo=timezone.utc),
            home=home,
            local_tz=timezone.utc,
            classify_project=kwargs.get("classify", lambda _hay, _profiles: "X"),
            make_event=make_test_event,
            noise_profile=kwargs.get("noise_profile", "strict"),
        )

    def test_returns_empty_when_no_logs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._collect(Path(tmp)), [])

    def test_keeps_workspace_path_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/renderer.log",
                [
                    "2026-05-29 09:00:00.123 [info] saved file "
                    "/Users/me/Workspace/Project/timelog-extract/core/cli.py"
                ],
            )
            out = self._collect(home, classify=lambda _h, _p: "Gittan CLI")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "Antigravity")
            self.assertEqual(out[0]["project"], "Gittan CLI")

    def test_maps_workspace_key_to_folder(self):
        # workspace.json may carry a "workspace" key instead of "folder".
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "b" * 32
            ws = self._base(home) / "User" / "workspaceStorage" / wid
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "workspace.json").write_text(
                json.dumps({"workspace": "file:///Users/me/Workspace/Project/timelog-extract"}),
                encoding="utf-8",
            )
            self._write_log(
                home,
                "main.log",
                [f"2026-05-29 09:06:00.000 [info] opened workspaceStorage/{wid}"],
            )
            out = self._collect(home, classify=lambda _h, _p: "Gittan CLI")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["project"], "Gittan CLI")

    def test_maps_workspace_id_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "a" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/timelog-extract")
            self._write_log(
                home,
                "main.log",
                [f"2026-05-29 09:05:00.000 [info] opened workspaceStorage/{wid}"],
            )
            out = self._collect(home, classify=lambda _h, _p: "Gittan CLI")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["project"], "Gittan CLI")

    def test_skips_language_server_heartbeat_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/exthost/google.antigravity/Antigravity IDE.log",
                [
                    "2026-05-29 09:10:00.000 [info] Starting language server process "
                    "/Users/me/Workspace/Project/timelog-extract"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_extension_activation_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/exthost/exthost.log",
                [
                    "2026-05-29 09:11:00.000 [info] ExtensionService#_doActivateExtension "
                    "google.antigravity /Users/me/Workspace/Project/timelog-extract"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_lenient_profile_keeps_extension_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/exthost/exthost.log",
                [
                    "2026-05-29 09:11:00.000 [info] ExtensionService#_doActivateExtension "
                    "google.antigravity /Users/me/Workspace/Project/timelog-extract"
                ],
            )
            self.assertEqual(len(self._collect(home, noise_profile="lenient")), 1)

    def test_skips_gittan_sync_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-29 09:12:00.000 [error] upload sync failed "
                    "/Users/me/.gittan-task/x/timelog_projects.json decisions-2026-05-29.json "
                    "/Users/me/Workspace/Project/timelog-extract"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_ide_internal_paths(self):
        # The IDE logs its own startup paths (extensions, html_artifacts) as
        # file:// URIs; these must not be attributed as project work.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            ext = home / ".antigravity-ide" / "extensions"
            art = home / ".gemini" / "antigravity-ide" / "html_artifacts"
            self._write_log(
                home,
                "main.log",
                [
                    f"2026-05-29 09:00:00.000 [info] initializing extensions file://{ext}",
                    f"2026-05-29 09:00:01.000 [info] Creating HTML artifacts directory: file://{art}",
                    f"2026-05-29 09:00:02.000 [info] app support {self._base(home)}/User/settings.json",
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_naive_iso_bracket_timestamp_defaults_to_local_tz(self):
        # A bracket ISO timestamp without offset parses naive; the collector
        # must default it to local_tz instead of raising on the window check.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "[2026-05-29T09:00:00] saved "
                    "/Users/me/Workspace/Project/timelog-extract/x.py"
                ],
            )
            out = self._collect(home, classify=lambda _h, _p: "Gittan CLI")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["timestamp"].tzinfo, timezone.utc)

    def test_filters_events_outside_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-28 09:00:00.000 [info] saved "
                    "/Users/me/Workspace/Project/timelog-extract/x.py"
                ],
            )
            self.assertEqual(self._collect(home), [])


if __name__ == "__main__":
    unittest.main()
