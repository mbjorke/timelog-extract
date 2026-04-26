"""Tests for setup wizard project config safety behavior."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rich.console import Console

from core.config import ENV_GITTAN_HOME, ENV_PROJECTS_CONFIG, resolve_projects_config_path
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
                with mock.patch.dict(os.environ, {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: tmp}, clear=False):
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
                with mock.patch.dict(os.environ, {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: tmp}, clear=False):
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
                with mock.patch.dict(os.environ, {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: tmp}, clear=False):
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
                    payload = json.loads(resolve_projects_config_path().read_text(encoding="utf-8"))
                project = payload["projects"][0]
                self.assertEqual(project["name"], "acme-tools")
                self.assertEqual(project["customer"], "example")
                self.assertIn("acme-tools", project["match_terms"])
                self.assertIn("example/acme-tools", project["match_terms"])
            finally:
                os.chdir(prev)

    def test_customer_seed_prompt_skipped_keeps_fallback_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps({"worklog": "TIMELOG.md", "projects": [{"name": "existing", "match_terms": ["existing"]}]}),
                encoding="utf-8",
            )
            with mock.patch("core.setup_projects_config_bootstrap.questionary.confirm") as confirm_mock:
                confirm_mock.return_value.ask.return_value = False
                result = ensure_projects_config(
                    console=Console(record=True),
                    yes=False,
                    dry_run=False,
                    bootstrap_root=tmp,
                    config_path=cfg,
                    timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                    looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
                )
            self.assertEqual(result.status, "PASS")
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(payload["projects"][0]["name"], "existing")
            self.assertNotIn("customer_seeds=", result.notes)

    def test_customer_seed_prompt_adds_one_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps({"worklog": "TIMELOG.md", "projects": [{"name": "existing", "match_terms": ["existing"]}]}),
                encoding="utf-8",
            )
            confirm_values = [True]
            text_values = ["Acme API", "Acme Client", ""]

            def _confirm(*_args, **_kwargs):
                value = confirm_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            def _text(*_args, **_kwargs):
                value = text_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            with mock.patch("core.setup_projects_config_bootstrap.questionary.confirm", side_effect=_confirm), mock.patch(
                "core.setup_projects_config_bootstrap.questionary.text", side_effect=_text
            ):
                result = ensure_projects_config(
                    console=Console(record=True),
                    yes=False,
                    dry_run=False,
                    bootstrap_root=tmp,
                    config_path=cfg,
                    timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                    looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
                )

            self.assertEqual(result.status, "PASS")
            self.assertIn("customer_seeds=1", result.notes)
            self.assertTrue(any("Customer bootstrap seeds saved" in step for step in result.next_steps))
            self.assertTrue(any("gittan report --today --source-summary" in step for step in result.next_steps))
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            projects = {project["name"]: project for project in payload["projects"]}
            self.assertIn("Acme API", projects)
            self.assertEqual(projects["Acme API"]["customer"], "Acme Client")
            self.assertIn("Acme API", projects["Acme API"]["match_terms"])

    def test_customer_seed_prompt_adds_three_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps({"worklog": "TIMELOG.md", "projects": [{"name": "existing", "match_terms": ["existing"]}]}),
                encoding="utf-8",
            )
            confirm_values = [True]
            text_values = [
                "Project One",
                "Customer One",
                "Project Two",
                "Customer Two",
                "Project Three",
                "Customer Three",
            ]

            def _confirm(*_args, **_kwargs):
                value = confirm_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            def _text(*_args, **_kwargs):
                value = text_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            with mock.patch("core.setup_projects_config_bootstrap.questionary.confirm", side_effect=_confirm), mock.patch(
                "core.setup_projects_config_bootstrap.questionary.text", side_effect=_text
            ):
                result = ensure_projects_config(
                    console=Console(record=True),
                    yes=False,
                    dry_run=False,
                    bootstrap_root=tmp,
                    config_path=cfg,
                    timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                    looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
                )

            self.assertEqual(result.status, "PASS")
            self.assertIn("customer_seeds=3", result.notes)
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            names = {project["name"] for project in payload["projects"]}
            self.assertTrue({"Project One", "Project Two", "Project Three"}.issubset(names))

    def test_customer_seed_merge_updates_existing_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "worklog": "TIMELOG.md",
                        "projects": [
                            {
                                "name": "Acme API",
                                "customer": "Locked Customer",
                                "match_terms": ["legacy-term"],
                                "tracked_urls": ["acme.example"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            confirm_values = [True]
            text_values = ["Acme API", "New Customer", ""]

            def _confirm(*_args, **_kwargs):
                value = confirm_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            def _text(*_args, **_kwargs):
                value = text_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            with mock.patch("core.setup_projects_config_bootstrap.questionary.confirm", side_effect=_confirm), mock.patch(
                "core.setup_projects_config_bootstrap.questionary.text", side_effect=_text
            ):
                result = ensure_projects_config(
                    console=Console(record=True),
                    yes=False,
                    dry_run=False,
                    bootstrap_root=tmp,
                    config_path=cfg,
                    timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                    looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
                )

            self.assertEqual(result.status, "PASS")
            self.assertIn("customer_seeds=1", result.notes)
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            project = payload["projects"][0]
            self.assertEqual(project["customer"], "Locked Customer")
            self.assertEqual(project["tracked_urls"], ["acme.example"])
            self.assertIn("legacy-term", project["match_terms"])
            self.assertIn("Acme API", project["match_terms"])

    def test_customer_seed_dry_run_shows_preview_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps({"worklog": "TIMELOG.md", "projects": [{"name": "existing", "match_terms": ["existing"]}]}),
                encoding="utf-8",
            )
            confirm_values = [True]
            text_values = ["Project Dry", "Customer Dry", ""]

            def _confirm(*_args, **_kwargs):
                value = confirm_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            def _text(*_args, **_kwargs):
                value = text_values.pop(0)
                return mock.Mock(ask=mock.Mock(return_value=value))

            with mock.patch("core.setup_projects_config_bootstrap.questionary.confirm", side_effect=_confirm), mock.patch(
                "core.setup_projects_config_bootstrap.questionary.text", side_effect=_text
            ):
                result = ensure_projects_config(
                    console=Console(record=True),
                    yes=False,
                    dry_run=True,
                    bootstrap_root=tmp,
                    config_path=cfg,
                    timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                    looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
                )
            self.assertEqual(result.status, "PASS (dry-run)")
            self.assertIn("customer_seeds=1", result.notes)
            self.assertTrue(any("Review captured project/customer seeds" in step for step in result.next_steps))
            self.assertTrue(cfg.exists())


if __name__ == "__main__":
    unittest.main()
