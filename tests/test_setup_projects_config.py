"""Tests for setup wizard project config safety behavior."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from rich.console import Console

from core.global_timelog_setup_lib import _ensure_minimal_projects_config


class SetupProjectsConfigTests(unittest.TestCase):
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
                result = _ensure_minimal_projects_config(Console(record=True), yes=True, dry_run=False)
                self.assertEqual(result, "PASS")
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
                result = _ensure_minimal_projects_config(Console(record=True), yes=True, dry_run=False)
                self.assertEqual(result, "PASS")
                backups = list(Path(tmp).glob("timelog_projects.backup-*.json"))
                self.assertEqual(len(backups), 1)
                recreated = json.loads(cfg.read_text(encoding="utf-8"))
                self.assertEqual(recreated["projects"][0]["name"], "default-project")
            finally:
                os.chdir(prev)


if __name__ == "__main__":
    unittest.main()
