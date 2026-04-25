from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.calibration.experiments import run_fixture, run_fixtures


class CliExperimentHarnessTests(unittest.TestCase):
    def test_fixture_evaluates_abc_variants(self):
        fixture_path = Path("tests/fixtures/experiments/month_trained_setup_fixture.json")
        payload = run_fixture(fixture_path)
        self.assertEqual(payload["fixture"], "month-trained-setup")
        self.assertIn(payload["winner"], {"A", "B", "C"})
        variants = [result["variant"] for result in payload["results"]]
        self.assertEqual(set(variants), {"A", "B", "C"})
        self.assertTrue(all("metrics" in result for result in payload["results"]))

    def test_directory_runner_returns_strict_aggregate(self):
        fixture_dir = Path("tests/fixtures/experiments")
        payload = run_fixtures(fixture_dir)
        self.assertIn("strict_pass", payload)
        self.assertEqual(len(payload["fixtures"]), 1)

    def test_invalid_command_is_rejected_by_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "bad.json"
            fixture.write_text(
                """
{
  "name": "bad-command",
  "target_project": "Acme",
  "profiles": [{"name":"Acme","match_terms":["acme"],"tracked_urls":[]}],
  "uncategorized_events": [{
    "source": "Chrome",
    "detail": "https://acme.example/x",
    "project": "Uncategorized",
    "timestamp": "2026-04-10T09:00:00+00:00"
  }],
  "command_sequence": ["gittan setup --yes"],
  "thresholds": {
    "events_classified_pct_min": 0.0,
    "suggestion_acceptance_ratio_min": 0.0,
    "setup_seconds_max": 999.0,
    "matched_hours_min": 0.0
  },
  "variant_inputs": {
    "setup_seconds": {"A": 10, "B": 10, "C": 10},
    "suggestion_acceptance_ratio": {"A": 1, "B": 1, "C": 1}
  }
}
                """.strip(),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                run_fixture(fixture)


if __name__ == "__main__":
    unittest.main()

