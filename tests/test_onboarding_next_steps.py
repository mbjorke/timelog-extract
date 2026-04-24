"""Tests for onboarding-oriented next-step guidance."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.onboarding_guidance import build_doctor_next_steps, build_setup_next_steps


class DoctorNextStepsTests(unittest.TestCase):
    def test_doctor_recommends_setup_when_basics_are_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=False,
                projects_config_ok=False,
                worklog_ok=False,
                match_terms_ok=False,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertNotIn("gittan setup", joined)
            self.assertNotIn("gittan projects --config", joined)
            self.assertIn(f"Create `{config_path.name}`", joined)
            self.assertIn(str(worklog_path), joined)
            self.assertIn("repo-specific `match_terms`", joined)
            self.assertIn("pipx ensurepath", joined)

    def test_doctor_recommends_first_report_when_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "timelog_projects.json"
            worklog_path = tmp_path / "TIMELOG.md"

            steps = build_doctor_next_steps(
                cli_on_path=True,
                projects_config_ok=True,
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
                worklog_ok=False,
                match_terms_ok=True,
                config_path=config_path,
                worklog_path=worklog_path,
            )

            joined = "\n".join(steps)
            self.assertNotIn("Run `gittan setup`", joined)
            self.assertIn(str(worklog_path), joined)


class SetupNextStepsTests(unittest.TestCase):
    def test_setup_dry_run_points_to_real_execution(self):
        steps = build_setup_next_steps(
            dry_run=True,
            projects_status="PASS (dry-run)",
            doctor_status="PASS (dry-run)",
            smoke_status="SKIPPED",
        )

        self.assertIn("gittan setup` without `--dry-run", steps[0])
        self.assertIn("gittan setup-global-timelog", "\n".join(steps))

    def test_setup_live_failure_points_back_to_doctor_and_report(self):
        steps = build_setup_next_steps(
            dry_run=False,
            projects_status="PASS",
            doctor_status="ACTION_REQUIRED",
            smoke_status="FAIL",
        )

        joined = "\n".join(steps)
        self.assertIn("gittan doctor", joined)
        self.assertIn("gittan report --today --source-summary", joined)

    def test_setup_live_all_pass_prefers_first_report_fallback(self):
        steps = build_setup_next_steps(
            dry_run=False,
            projects_status="PASS",
            doctor_status="PASS",
            smoke_status="PASS",
        )
        self.assertEqual(
            steps,
            [
                "Run `gittan report --today --source-summary` for your first report.",
                "Use `gittan projects` later if you want to refine project matching.",
            ],
        )

    def test_setup_fast_adds_global_timelog_followup_hint(self):
        steps = build_setup_next_steps(
            dry_run=False,
            projects_status="PASS",
            doctor_status="PASS",
            smoke_status="SKIPPED",
            fast=True,
        )
        joined = "\n".join(steps)
        self.assertIn("gittan setup-global-timelog", joined)


if __name__ == "__main__":
    unittest.main()
