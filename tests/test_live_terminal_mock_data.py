"""Ensure demo fixture is stable and used by stub outputs."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.live_terminal.mock_data import load_demo_mock_data
from core.live_terminal.stub_output import (
    _doctor_output,
    _json_output,
    _source_summary_output,
    demo_stub_output,
)


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


class DoctorOutputTests(unittest.TestCase):
    """Tests for _doctor_output() which is now fixture-driven."""

    def test_doctor_output_uses_fixture_title(self):
        out = _doctor_output()
        fixture = load_demo_mock_data()
        expected_title = fixture["doctor"]["title"]
        self.assertIn(expected_title, out)

    def test_doctor_output_contains_all_fixture_rows(self):
        fixture = load_demo_mock_data()
        out = _doctor_output()
        for name, status in fixture["doctor"]["rows"]:
            self.assertIn(name, out, msg=f"Row name '{name}' not in doctor output")
            self.assertIn(status, out, msg=f"Row status '{status}' not in doctor output")

    def test_doctor_output_ends_with_newline(self):
        self.assertTrue(_doctor_output().endswith("\n"))

    def test_source_summary_output_starts_with_header(self):
        out = _source_summary_output()
        self.assertTrue(out.startswith("Source summary (demo fixture)"))

    def test_source_summary_output_ends_with_newline(self):
        self.assertTrue(_source_summary_output().endswith("\n"))

    def test_json_output_is_parseable(self):
        out = _json_output()
        parsed = json.loads(out)
        self.assertIsInstance(parsed, dict)

    def test_json_output_matches_fixture(self):
        fixture = load_demo_mock_data()
        out = _json_output()
        parsed = json.loads(out)
        self.assertEqual(parsed, fixture["truth_payload"])

    def test_demo_stub_output_doctor_uses_fixture_title(self):
        out = demo_stub_output("gittan doctor")
        fixture = load_demo_mock_data()
        self.assertIn(fixture["doctor"]["title"], out)


class MockDataEnvOverrideTests(unittest.TestCase):
    """Tests for load_demo_mock_data() env var override."""

    def test_env_override_loads_custom_fixture(self):
        custom = {
            "version": 2,
            "doctor": {"title": "Custom Health (test)", "rows": [["Custom Source", "CUSTOM"]]},
            "source_summary": {"rows": [["CustomSource", 99]], "total": 99},
            "truth_payload": {"schema": "test", "version": 2, "demo": True, "totals": {"event_count": 1, "hours_estimated": 0}},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(custom, tmp)
            tmp_path = tmp.name
        try:
            # Clear cache so env override takes effect
            load_demo_mock_data.cache_clear()
            with patch.dict(os.environ, {"GITTAN_DEMO_MOCK_DATA": tmp_path}):
                result = load_demo_mock_data()
            self.assertEqual(result["version"], 2)
            self.assertEqual(result["doctor"]["title"], "Custom Health (test)")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
            load_demo_mock_data.cache_clear()

    def test_missing_custom_fixture_raises_file_not_found(self):
        load_demo_mock_data.cache_clear()
        with patch.dict(os.environ, {"GITTAN_DEMO_MOCK_DATA": "/nonexistent/path/fixture.json"}):
            with self.assertRaises(FileNotFoundError):
                load_demo_mock_data()
        load_demo_mock_data.cache_clear()


if __name__ == "__main__":
    unittest.main()