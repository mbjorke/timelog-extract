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
        self.assertIn("Source summary (demo fixture)", out)
        lines = out.splitlines()
        for source, count in fixture["source_summary"]["rows"]:
            expected_line = f"{source:<20} {int(count)}"
            self.assertIn(expected_line, lines)
        self.assertIn(f"Total: {fixture['source_summary']['total']}", out)

    def test_stub_json_matches_fixture_payload(self):
        fixture = load_demo_mock_data()
        out = demo_stub_output("gittan report --today --format json")
        payload = json.loads(out)
        self.assertEqual(payload, fixture["truth_payload"])


if __name__ == "__main__":
    unittest.main()
