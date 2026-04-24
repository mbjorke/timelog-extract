"""Tests for setup wizard project config safety behavior."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from rich.console import Console

from core.global_timelog_setup_lib import _ensure_minimal_projects_config
from core.setup_projects_config_bootstrap import ensure_projects_config


class SetupProjectsConfigTests(unittest.TestCase):
    def test_ensure_projects_config_creates_missing_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "nested" / "profile" / "timelog_projects.json"
            result = ensure_projects_config(
                console=Console(record=True),
                yes=True,
                dry_run=False,
                bootstrap_root=tmp,
                config_path=cfg,
                timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
            )
            self.assertEqual(result.status, "PASS")
            self.assertTrue(cfg.is_file())

    def test_existing_valid_config_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = Path.cwd()
            try:
                os.chdir(tmp)
                cfg = Path(tmp) / "timelog_projects.json"
                cfg.write_text(
                    json.dumps(
                        {
                            "worklog": "TIMELOG.md",
                            "projects": [{"name": "keep-me", "match_terms": ["keep"]}],
                        }
                    ),
                    encoding="utf-8",
                )
                status, notes, _steps = _ensure_minimal_projects_config(
                    Console(record=True),
                    yes=True,
                    dry_run=False,
                    bootstrap_root=tmp,
                )
                self.assertEqual(status, "PASS")
                self.assertIn("discovered=0", notes)
                payload = json.loads(cfg.read_text(encoding="utf-8"))
                self.assertEqual(payload["projects"][0]["name"], "keep-me")
                self.assertEqual(list(Path(tmp).glob("timelog_projects.backup-*.json")), [])
            finally:
                os.chdir(prev)

    def test_invalid_config_is_backed_up_and_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = Path.cwd()
            try:
                os.chdir(tmp)
                cfg = Path(tmp) / "timelog_projects.json"
                cfg.write_text("{not valid json", encoding="utf-8")
                status, notes, _steps = _ensure_minimal_projects_config(
                    Console(record=True),
                    yes=True,
                    dry_run=False,
                    bootstrap_root=tmp,
                )
                self.assertEqual(status, "PASS")
                self.assertIn("fallback profile used", notes)
                backups = list(Path(tmp).glob("timelog_projects.backup-*.json"))
                self.assertEqual(len(backups), 1)
                recreated = json.loads(cfg.read_text(encoding="utf-8"))
                self.assertEqual(recreated["projects"][0]["name"], "default-project")
            finally:
                os.chdir(prev)

    def test_bootstrap_uses_git_aware_defaults_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = Path.cwd()
            try:
                os.chdir(tmp)
                subprocess.run(["git", "init"], check=True, capture_output=True, text=True)
                subprocess.run(
                    ["git", "remote", "add", "origin", "https://github.com/example/acme-tools.git"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                status, notes, _steps = _ensure_minimal_projects_config(
                    Console(record=True),
                    yes=True,
                    dry_run=False,
                    bootstrap_root=tmp,
                )
                self.assertEqual(status, "PASS")
                self.assertIn("discovered=1", notes)
                from core.config import resolve_projects_config_path

                payload = json.loads(resolve_projects_config_path().read_text(encoding="utf-8"))
                project = payload["projects"][0]
                self.assertEqual(project["name"], "acme-tools")
                self.assertEqual(project["customer"], "example")
                self.assertIn("acme-tools", project["match_terms"])
                self.assertIn("example/acme-tools", project["match_terms"])
            finally:
                os.chdir(prev)


if __name__ == "__main__":
    unittest.main()
