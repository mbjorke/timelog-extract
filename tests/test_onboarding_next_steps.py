"""Tests for onboarding-oriented next-step guidance."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.onboarding_guidance import build_doctor_next_steps, build_setup_next_steps


class DoctorNextStepsTests(unittest.TestCase):
    def test_doctor_recommends_setup_when_basics_are_missing(self):
        steps = build_doctor_next_steps(
            cli_on_path=False,
            projects_config_ok=False,
            worklog_ok=False,
            config_path=Path("/tmp/timelog_projects.json"),
            worklog_path=Path("/tmp/TIMELOG.md"),
        )

        joined = "\n".join(steps)
        self.assertIn("gittan setup", joined)
        self.assertIn("gittan projects --config /tmp/timelog_projects.json", joined)
        self.assertIn("/tmp/TIMELOG.md", joined)
        self.assertIn("pipx ensurepath", joined)

    def test_doctor_recommends_first_report_when_ready(self):
        steps = build_doctor_next_steps(
            cli_on_path=True,
            projects_config_ok=True,
            worklog_ok=True,
            config_path=Path("/tmp/timelog_projects.json"),
            worklog_path=Path("/tmp/TIMELOG.md"),
        )

        self.assertEqual(
            steps,
            [
                "Run `gittan report --today --source-summary` for a first local report.",
                "Use `gittan projects` if you want to refine project matching before reporting.",
            ],
        )


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
        self.assertIn("gittan projects", joined)
        self.assertIn("gittan report --today --source-summary", joined)


if __name__ == "__main__":
    unittest.main()
