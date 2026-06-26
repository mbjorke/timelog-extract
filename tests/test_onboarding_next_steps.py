"""Tests for onboarding-oriented next-step guidance."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.onboarding_guidance import (
    build_doctor_next_steps,
    build_setup_next_steps,
    rule_hygiene_needed_for_config,
)


class DoctorNextStepsTests(unittest.TestCase):
    def test_doctor_recommends_setup_dry_run_when_config_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=True,
                projects_config_ok=False,
                config_valid=False,
                worklog_ok=False,
                match_terms_ok=True,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertIn("gittan setup --dry-run", joined)
            self.assertIn("doctor does not write config", joined)
            self.assertNotIn("gittan projects --config", joined)

    def test_doctor_recommends_manual_create_when_cli_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=False,
                projects_config_ok=False,
                config_valid=False,
                worklog_ok=False,
                match_terms_ok=True,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertNotIn("gittan setup", joined)
            self.assertIn(f"Create `{config_path.name}`", joined)
            self.assertIn("pipx ensurepath", joined)

    def test_doctor_recommends_setup_dry_run_for_invalid_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            config_path.write_text("{not-json", encoding="utf-8")
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=True,
                projects_config_ok=True,
                config_valid=False,
                worklog_ok=True,
                match_terms_ok=True,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertIn("gittan setup --dry-run", joined)
            self.assertIn("timestamped backup", joined)

    def test_doctor_points_weak_rules_to_review_and_audit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            config_path.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "name": "Alpha",
                                "match_terms": ["koden"],
                                "tracked_urls": ["https://chatgpt.com"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            worklog_path = tmp_path / "TIMELOG.md"

            self.assertTrue(rule_hygiene_needed_for_config(config_path))
            steps = build_doctor_next_steps(
                cli_on_path=True,
                projects_config_ok=True,
                config_valid=True,
                worklog_ok=True,
                match_terms_ok=True,
                rule_hygiene_needed=True,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertIn("gittan review", joined)
            self.assertIn("gittan projects-audit", joined)

    def test_doctor_git_coverage_warn_suggests_review_and_audit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            config_path.write_text(
                json.dumps({"projects": [{"name": "Alpha", "match_terms": ["alpha"]}]}),
                encoding="utf-8",
            )
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=True,
                projects_config_ok=True,
                config_valid=True,
                worklog_ok=True,
                match_terms_ok=False,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertIn("gittan review", joined)
            self.assertIn("gittan projects-audit", joined)

    def test_doctor_recommends_first_report_when_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=True,
                projects_config_ok=True,
                config_valid=True,
                worklog_ok=True,
                match_terms_ok=True,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            self.assertEqual(
                steps,
                [
                    "Run `gittan report --today --source-summary` for a first local report.",
                    "Use `gittan projects` if you want to refine project matching before reporting.",
                ],
            )

    def test_doctor_does_not_recommend_setup_when_only_worklog_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=True,
                projects_config_ok=True,
                config_valid=True,
                worklog_ok=False,
                match_terms_ok=True,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertNotIn("Run `gittan setup`", joined)
            self.assertIn(str(worklog_path), joined)
            self.assertIn("legacy fallback may resolve to `TIMELOG.md`", joined)


class SetupNextStepsTests(unittest.TestCase):
    def test_setup_dry_run_points_to_real_execution_and_review(self):
        steps = build_setup_next_steps(
            dry_run=True,
            projects_status="PASS (dry-run)",
            mapping_status="PASS (dry-run)",
            doctor_status="PASS (dry-run)",
            smoke_status="SKIPPED",
            has_project_buckets=True,
        )

        joined = "\n".join(steps)
        self.assertIn("Next: run `gittan setup` without `--dry-run`", steps[0])
        self.assertIn("gittan review", joined)
        self.assertIn("gittan review --json", joined)
        self.assertIn("gittan setup-global-timelog", joined)
        self.assertIn("gittan report --today --source-summary", joined)

    def test_setup_live_failure_points_back_to_doctor_and_report(self):
        steps = build_setup_next_steps(
            dry_run=False,
            projects_status="PASS",
            mapping_status="PASS",
            doctor_status="ACTION_REQUIRED",
            smoke_status="FAIL",
        )

        joined = "\n".join(steps)
        self.assertIn("gittan doctor", joined)
        self.assertIn("gittan report --today --source-summary", joined)

    def test_setup_live_all_pass_prefers_review_then_report(self):
        steps = build_setup_next_steps(
            dry_run=False,
            projects_status="PASS",
            mapping_status="PASS",
            doctor_status="PASS",
            smoke_status="PASS",
            has_project_buckets=True,
        )
        self.assertEqual(
            steps,
            [
                "Next: run `gittan review` to map URL domains to project buckets.",
                "Optional: `gittan review --json` for read-only URL mapping candidates.",
                "Then: run `gittan report --today --source-summary` for your first report.",
            ],
        )

    def test_setup_fast_adds_global_timelog_followup_hint(self):
        steps = build_setup_next_steps(
            dry_run=False,
            projects_status="PASS",
            mapping_status="PASS",
            doctor_status="PASS",
            smoke_status="SKIPPED",
            fast=True,
            has_project_buckets=True,
        )
        joined = "\n".join(steps)
        self.assertIn("gittan setup-global-timelog", joined)

    def test_setup_fast_dry_run_prefers_fast_replay_command(self):
        steps = build_setup_next_steps(
            dry_run=True,
            projects_status="PASS (dry-run)",
            mapping_status="PASS (dry-run)",
            doctor_status="PASS (dry-run)",
            smoke_status="SKIPPED",
            fast=True,
            has_project_buckets=True,
        )
        self.assertIn("Next: run `gittan setup --fast` without `--dry-run`", steps[0])

    def test_setup_mapping_skip_points_to_plain_setup_retry(self):
        steps = build_setup_next_steps(
            dry_run=False,
            projects_status="PASS",
            mapping_status="SKIPPED",
            doctor_status="PASS",
            smoke_status="PASS",
        )
        self.assertIn("run `gittan setup` again and complete the project mapping step", "\n".join(steps))


if __name__ == "__main__":
    unittest.main()
