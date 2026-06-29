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
from core.setup_projects_config_bootstrap import (
    _provision_missing_project_worklog_paths,
    ensure_projects_config,
)


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
                                "projects": [
                                    {
                                        "name": "keep-me",
                                        "worklog": "~/.gittan/worklogs/keep-me.md",
                                        "match_terms": ["keep"],
                                    }
                                ],
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
                self.assertIn("merge skipped", notes.lower())
                payload = json.loads(cfg.read_text(encoding="utf-8"))
                self.assertEqual(payload["projects"][0]["name"], "keep-me")
                self.assertEqual(list(Path(tmp).glob("timelog_projects.backup-*.json")), [])
                self.assertEqual(list(Path(tmp).glob("timelog_projects.backup.*.json")), [])
            finally:
                os.chdir(prev)

    def test_existing_project_worklog_content_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            worklog_dir = Path(tmp) / "worklogs"
            worklog_dir.mkdir(parents=True, exist_ok=True)
            existing_worklog = worklog_dir / "keep-me.md"
            original = "## 2026-05-06 16:00\n- Existing entry\n"
            existing_worklog.write_text(original, encoding="utf-8")
            cfg.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "name": "keep-me",
                                "customer": "customer-a.test",
                                "worklog": str(existing_worklog),
                                "match_terms": ["keep-me"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
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
            self.assertEqual(existing_worklog.read_text(encoding="utf-8"), original)

    def test_dry_run_leaves_config_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            original = '{"projects": [{"name": "keep-me", "match_terms": ["keep"]}]}'
            cfg.write_text(original, encoding="utf-8")
            result = ensure_projects_config(
                console=Console(record=True),
                yes=True,
                dry_run=True,
                bootstrap_root=tmp,
                config_path=cfg,
                timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
            )
            self.assertEqual(result.status, "PASS (dry-run)")
            self.assertEqual(cfg.read_text(encoding="utf-8"), original)
            joined = "\n".join(result.next_steps)
            self.assertIn("--bootstrap-repos", joined)
            self.assertIn("gittan review", joined)

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
                self.assertIn("worklog", project)
                self.assertTrue(Path(project["worklog"]).exists())
                self.assertIn("acme-tools", project["match_terms"])
                self.assertIn("example/acme-tools", project["match_terms"])
            finally:
                os.chdir(prev)

    def test_customer_seed_prompt_skipped_keeps_fallback_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "name": "existing",
                                "worklog": "~/.gittan/worklogs/existing.md",
                                "match_terms": ["existing"],
                            }
                        ]
                    }
                ),
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

    def test_setup_no_longer_prompts_for_manual_customer_project_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "name": "existing",
                                "worklog": "~/.gittan/worklogs/existing.md",
                                "match_terms": ["existing"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch("core.setup_projects_config_bootstrap.questionary.text") as text_mock, mock.patch(
                "core.setup_projects_config_bootstrap.questionary.confirm"
            ) as confirm_mock:
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
            self.assertNotIn("customer_seeds=", result.notes)
            self.assertTrue(cfg.exists())
            text_mock.assert_not_called()
            confirm_mock.assert_not_called()
            # Existing project remains; bootstrap no longer asks for Project 1/2/3 seeds.
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(payload["projects"][0]["name"], "existing")


class SetupConfigWriteGateTests(unittest.TestCase):
    def test_bootstrap_repos_merges_existing_valid_config_with_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "name": "existing-repo",
                                "customer": "customer-a.test",
                                "match_terms": ["existing-repo"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            repo_dir = Path(tmp) / "existing-repo"
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/example/existing-repo.git"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            with mock.patch("core.setup_projects_config_bootstrap.questionary.confirm") as confirm_mock:
                confirm_mock.return_value.ask.return_value = True
                result = ensure_projects_config(
                    console=Console(record=True),
                    yes=True,
                    dry_run=False,
                    bootstrap_repos=True,
                    bootstrap_root=tmp,
                    config_path=cfg,
                    timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                    looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
                )
            self.assertEqual(result.status, "PASS")
            backups = list(Path(tmp).glob("timelog_projects.backup.*.json"))
            self.assertEqual(len(backups), 1)
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertEqual(payload["projects"][0]["name"], "existing-repo")
            self.assertIn("example/existing-repo", payload["projects"][0]["match_terms"])

    def test_yes_without_bootstrap_repos_does_not_merge_valid_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            original_text = json.dumps(
                {
                    "projects": [
                        {
                            "name": "keep-me",
                            "match_terms": ["keep"],
                        }
                    ]
                }
            )
            cfg.write_text(original_text, encoding="utf-8")
            repo_dir = Path(tmp) / "other-repo"
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
            result = ensure_projects_config(
                console=Console(record=True),
                yes=True,
                dry_run=False,
                bootstrap_repos=False,
                bootstrap_root=tmp,
                config_path=cfg,
                timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
            )
            self.assertTrue(result.merge_skipped)
            self.assertEqual(cfg.read_text(encoding="utf-8"), original_text)
            self.assertEqual(len(list(Path(tmp).glob("timelog_projects.backup.*.json"))), 0)

    def test_yes_with_bootstrap_repos_still_requires_merge_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            original_text = json.dumps(
                {
                    "projects": [
                        {
                            "name": "keep-me",
                            "match_terms": ["keep"],
                        }
                    ]
                }
            )
            cfg.write_text(original_text, encoding="utf-8")
            with mock.patch("core.setup_projects_config_bootstrap.questionary.confirm") as confirm_mock:
                confirm_mock.return_value.ask.return_value = False
                result = ensure_projects_config(
                    console=Console(record=True),
                    yes=True,
                    dry_run=False,
                    bootstrap_repos=True,
                    bootstrap_root=tmp,
                    config_path=cfg,
                    timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                    looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
                )
            self.assertEqual(result.status, "SKIPPED")
            self.assertTrue(result.merge_skipped)
            self.assertEqual(cfg.read_text(encoding="utf-8"), original_text)

    def test_dry_run_bootstrap_repos_next_step_preserves_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps({"projects": [{"name": "keep-me", "match_terms": ["keep"]}]}),
                encoding="utf-8",
            )
            result = ensure_projects_config(
                console=Console(record=True),
                yes=True,
                dry_run=True,
                bootstrap_repos=True,
                bootstrap_root=tmp,
                config_path=cfg,
                timestamped_backup_path_fn=lambda path: path.with_suffix(".backup.json"),
                looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
            )
            joined = "\n".join(result.next_steps)
            self.assertIn("gittan setup --bootstrap-repos", joined)
            self.assertNotIn("without `--dry-run` for non-destructive apply", joined)


class SetupProjectsConfigProvisionTests(unittest.TestCase):
    def test_provision_missing_project_worklog_paths_creates_missing_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text('{"projects": []}', encoding="utf-8")
            existing = Path(tmp) / "worklogs" / "existing.md"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("# existing\n", encoding="utf-8")
            payload = {
                "projects": [
                    {"name": "missing-a"},
                    {"name": "existing", "worklog": str(existing)},
                ]
            }
            touched = _provision_missing_project_worklog_paths(payload=payload, config_path=cfg)
            self.assertEqual(len(touched), 1)
            self.assertTrue(touched[0].exists())
            self.assertEqual(existing.read_text(encoding="utf-8"), "# existing\n")



if __name__ == "__main__":
    unittest.main()
