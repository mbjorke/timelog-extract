"""Ensure demo fixture is stable and used by stub outputs."""

from __future__ import annotations

import json
import unittest

from core.live_terminal.mock_data import load_demo_mock_data
from core.live_terminal.stub_output import demo_stub_output


class LiveTerminalMockDataTests(unittest.TestCase):
    def test_fixture_loads_expected_shape(self):
        fixture = load_demo_mock_data()
        self.assertEqual(fixture.get("version"), 1)
        self.assertIn("doctor", fixture)
        self.assertIn("source_summary", fixture)
        self.assertIn("truth_payload", fixture)

    def test_stub_source_summary_uses_fixture_counts(self):
        fixture = load_demo_mock_data()
        out = demo_stub_output("gittan report --today --source-summary")
        self.assertIn("Gittan report — today (demo fixture)", out)
        self.assertIn("Source summary", out)
        lines = out.splitlines()
        for source, count in fixture["source_summary"]["rows"]:
            expected_line = f"{source:<22} {int(count)} events"
            self.assertIn(expected_line, lines)
        self.assertIn(f"Total: {fixture['source_summary']['total']}", out)
        self.assertIn("Observed time:", out)
        self.assertIn("Classified candidates:", out)
        self.assertIn("Approved invoice time:", out)
        self.assertIn("Gittan organizes evidence", out)

    def test_stub_doctor_output_is_demo_ready(self):
        out = demo_stub_output("gittan doctor")
        self.assertIn("Gittan doctor — demo environment", out)
        self.assertIn("Project config", out)
        self.assertIn("Approval workflow", out)
        self.assertIn("classified time is not invoice truth", out)
        self.assertIn("Next: run `gittan report --today --source-summary`", out)

    def test_stub_status_output_matches_truth_model(self):
        out = demo_stub_output("gittan status")
        self.assertIn("Gittan Status — today (demo fixture)", out)
        self.assertIn("Timeframe prompt: Today selected for demo.", out)
        self.assertIn("Hours Summary (unique timeline)", out)
        self.assertIn("Classified candidates:", out)
        self.assertIn("Approved invoice time:", out)
        self.assertIn("Invoice approval is still manual", out)

    def test_stub_setup_outputs_are_safe_and_demo_ready(self):
        dry_run = demo_stub_output("gittan setup --dry-run")
        self.assertIn("Gittan setup — dry run (demo fixture)", dry_run)
        self.assertIn("No files were changed.", dry_run)

        setup = demo_stub_output("gittan setup")
        self.assertIn("Gittan setup — demo fixture", setup)
        self.assertIn("Global timelog           SKIPPED — demo mode", setup)
        self.assertIn("Then: run `gittan report --today --source-summary`", setup)

    def test_stub_bare_report_selects_today_for_demo(self):
        out = demo_stub_output("gittan report")
        self.assertIn("Timeframe prompt: Today selected for demo.", out)
        self.assertIn("Gittan report — today (demo fixture)", out)
        self.assertIn("Gittan organizes evidence", out)

    def test_stub_json_matches_fixture_payload(self):
        fixture = load_demo_mock_data()
        out = demo_stub_output("gittan report --today --format json")
        payload = json.loads(out)
        self.assertEqual(payload, fixture["truth_payload"])
        self.assertEqual(payload["truth_model"]["approval_state"], "human_review_required")


if __name__ == "__main__":
    unittest.main()
