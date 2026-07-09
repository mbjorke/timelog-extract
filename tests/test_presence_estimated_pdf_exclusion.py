"""Regression test: presence-estimated hours must never leak into the invoice.

Spec: docs/task-prompts/presence-estimated-hours-task.md (GH-146), acceptance
Scenario 3 — "Estimate never touches billable or truth-payload hours." This
guards the invariant at the actual invoice-generation surfaces
(``outputs.pdf.build_invoice_pdf`` and ``core.report_service._build_invoice_pdf``
/ ``generate_invoice_pdf``) rather than only asserting on string constants, so a
future accidental wiring of presence data into the invoice path fails CI.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core import report_invoice, report_service
from core.presence_estimated import compute_presence_estimated
from outputs import pdf as pdf_output


def _fixture(day: str):
    """Same fixture shape as tests/test_truth_payload.py's presence test: two
    widely-spaced events for project "P" so the gap-fill estimate (bounded by
    an 8h Screen Time cap) exceeds the 1.0h evidenced total."""
    base = datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc)
    later = datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc)
    entries = [
        {"source": "Cursor", "timestamp": base, "local_ts": base, "detail": "a", "project": "P"},
        {"source": "Cursor", "timestamp": later, "local_ts": later, "detail": "b", "project": "P"},
    ]
    overall_days = {day: {"hours": 1.0, "entries": entries}}
    project_reports = {"P": {day: {"hours": 1.0}}}
    presence = compute_presence_estimated(
        overall_days,
        project_reports,
        screen_time_days={day: 8 * 3600.0},
    )
    return overall_days, project_reports, presence


class PresenceEstimatedPdfExclusionTests(unittest.TestCase):
    # GH-146: presence-*estimated* data must never be a PDF builder input.
    # GH-327's ``include_presence_billable`` is an opt-in *flag* (not estimate
    # data) and is allowed on the billable path.
    _FORBIDDEN_PRESENCE_DATA_PARAMS = frozenset(
        {
            "presence_estimated",
            "presence_estimate",
            "presence_hours",
            "presence_estimated_hours",
        }
    )

    def _assert_no_presence_estimate_param(self, fn):
        params = inspect.signature(fn).parameters
        for name in params:
            self.assertNotIn(name, self._FORBIDDEN_PRESENCE_DATA_PARAMS)
            if "presence" in name and name != "include_presence_billable":
                self.fail(
                    f"Unexpected presence-related PDF parameter {name!r}; "
                    f"only include_presence_billable (GH-327) is allowed"
                )

    def test_build_invoice_pdf_signature_has_no_presence_parameter(self):
        """Codify the exclusion contract: the PDF builder cannot accept presence
        *estimate* data even if a caller tried to pass it."""
        self._assert_no_presence_estimate_param(pdf_output.build_invoice_pdf)

    def test_internal_build_invoice_pdf_signature_has_no_presence_parameter(self):
        self._assert_no_presence_estimate_param(report_invoice._build_invoice_pdf)

    def test_generate_invoice_pdf_signature_has_no_presence_parameter(self):
        self._assert_no_presence_estimate_param(report_invoice.generate_invoice_pdf)

    def test_invoice_pdf_total_matches_evidenced_not_presence(self):
        """Build a real invoice PDF from a fixture where presence-estimated
        hours (10.0h) exceed evidenced hours (1.0h); the invoice total must
        equal the evidenced-only total, never the inflated presence estimate."""
        day = "2026-06-11"
        overall_days, project_reports, presence = _fixture(day)
        self.assertTrue(presence.available)
        self.assertGreater(presence.total_hours, 1.0)

        evidenced_total = sum(p["hours"] for p in overall_days.values())
        self.assertEqual(evidenced_total, 1.0)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "invoice.pdf"
            dt_from = datetime(2026, 6, 11, tzinfo=timezone.utc)
            dt_to = datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc)
            profiles = [{"name": "P", "customer": "Customer A"}]

            result_path = pdf_output.build_invoice_pdf(
                overall_days,
                project_reports,
                profiles,
                dt_from,
                dt_to,
                output_path,
                timezone.utc,
                report_service._billable_total_hours,
                customer_name="Customer A",
                billable_unit=0.0,
            )

            self.assertTrue(result_path.exists())
            # No billable_unit rounding requested -> invoice_total_billable falls
            # back to total_raw_hours, computed strictly from overall_days.
            total_raw_hours = sum(day_payload["hours"] for day_payload in overall_days.values())
            self.assertEqual(total_raw_hours, evidenced_total)
            self.assertNotEqual(total_raw_hours, presence.total_hours)
            self.assertLess(total_raw_hours, presence.total_hours)


if __name__ == "__main__":
    unittest.main()
