from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.vscode import _VSCODE_NOISE, SOURCE_NAME, collect_vscode
from collectors.vscode_fork import collect_fork_logs
from tests.event_helpers import make_test_event


class VSCodeCollectorTests(unittest.TestCase):
    def _base(self, home: Path, app: str = "Code") -> Path:
        return home / "Library" / "Application Support" / app

    def _write_workspace(self, home: Path, wid: str, folder_path: str, app: str = "Code") -> None:
        ws = self._base(home, app) / "User" / "workspaceStorage" / wid
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "workspace.json").write_text(
            json.dumps({"folder": f"file://{folder_path}"}), encoding="utf-8"
        )

    def _write_log(self, home: Path, rel: str, lines: list[str], app: str = "Code") -> None:
        p = self._base(home, app) / "logs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _collect(self, home: Path, **kwargs):
        return collect_vscode(
            profiles=[],
            dt_from=datetime(2026, 5, 28, 0, 0, tzinfo=timezone.utc),
            dt_to=datetime(2026, 5, 28, 23, 59, tzinfo=timezone.utc),
            home=home,
            local_tz=timezone.utc,
            classify_project=kwargs.get("classify", lambda _hay, _profiles: "X"),
            make_event=make_test_event,
            noise_profile=kwargs.get("noise_profile", "strict"),
        )

    def test_returns_empty_when_no_logs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._collect(Path(tmp)), [])

    def test_keeps_user_editing_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-28 09:00:00.000 [info] editing src/api.ts "
                    "/Users/me/Workspace/Project/project-alpha"
                ],
            )
            out = self._collect(home, classify=lambda _h, _p: "Project Alpha")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "VS Code")
            self.assertEqual(out[0]["project"], "Project Alpha")
            self.assertEqual(out[0]["anchors"]["dir"], "project-alpha")

    def test_maps_workspace_id_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wid = "a" * 32
            self._write_workspace(home, wid, "/Users/me/Workspace/Project/project-alpha")
            self._write_log(
                home,
                "window1/renderer.log",
                [f"2026-05-28 09:05:00.000 [info] focus workspaceStorage/{wid}"],
            )
            out = self._collect(home, classify=lambda _h, _p: "Project Alpha")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["project"], "Project Alpha")

    def test_scans_insiders_base_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-28 09:14:00.000 [info] editing src/api.ts "
                    "/Users/me/Workspace/Project/project-beta"
                ],
                app="Code - Insiders",
            )
            out = self._collect(home, classify=lambda _h, _p: "Project Beta")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "VS Code")
            self.assertEqual(out[0]["project"], "Project Beta")

    def test_skips_extension_activation_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "window1/exthost/exthost.log",
                [
                    "2026-05-28 09:10:00.000 [info] ExtensionService#_doActivateExtension "
                    "/Users/me/Workspace/Project/project-alpha"
                ],
            )
            self.assertEqual(self._collect(home), [])

    def test_skips_app_support_internal_paths(self):
        # Real macOS internals include a space ("Application Support"). The shared
        # /Users/... extractor truncates there; line-level internal matching must
        # still drop the event (regression for PR #422 / kanin finding).
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            logs = home / "logs"
            logs.mkdir(parents=True)
            (logs / "main.log").write_text(
                "2026-05-28 09:13:30.000 [info] wrote settings "
                "/Users/me/Library/Application Support/Code/User/settings.json\n",
                encoding="utf-8",
            )
            out = collect_fork_logs(
                [],
                datetime(2026, 5, 28, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 28, 23, 59, tzinfo=timezone.utc),
                home,
                timezone.utc,
                lambda *_: "X",
                make_test_event,
                source_name=SOURCE_NAME,
                base_dirs=[home],
                noise_fn=_VSCODE_NOISE,
                internal_paths=["/Users/me/Library/Application Support/Code"],
            )
            self.assertEqual(out, [])

    def test_ultra_strict_keeps_path_containing_telemetry_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._write_log(
                home,
                "main.log",
                [
                    "2026-05-28 09:20:00.000 [info] editing "
                    "/Users/me/Workspace/Project/telemetry-dashboard/src/app.ts"
                ],
            )
            out = self._collect(home, noise_profile="ultra-strict")
            self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
