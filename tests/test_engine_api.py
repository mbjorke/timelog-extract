"""Tests for the extension-facing engine API boundary."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from core.engine_api import run_report_payload, run_report_with_optional_pdf
from core.truth_payload import TRUTH_PAYLOAD_VERSION


class EngineApiTests(unittest.TestCase):
    def test_run_report_payload_is_versioned_dict(self):
        # Use the repo's default config path; this should be stable in-tree.
        # Keep the run quiet: boundary should be callable in extension contexts.
        buf = io.StringIO()
        with redirect_stdout(buf):
            payload = run_report_payload(
                "timelog_projects.json",
                None,
                None,
                {"today": True, "quiet": True, "screen_time": "off"},
            )
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("schema"), "timelog_extract.truth_payload")
        self.assertEqual(payload.get("version"), TRUTH_PAYLOAD_VERSION)
        self.assertIn("days", payload)

    def test_run_report_with_optional_pdf_without_pdf(self):
        out = run_report_with_optional_pdf(
            "timelog_projects.json",
            None,
            None,
            {"today": True, "quiet": True, "screen_time": "off"},
            generate_pdf=False,
        )
        self.assertIn("payload", out)
        self.assertIn("pdf_path", out)
        self.assertIsNone(out["pdf_path"])
        self.assertIn("schema", out["payload"])
        self.assertIn("version", out["payload"])


if __name__ == "__main__":
    unittest.main()

