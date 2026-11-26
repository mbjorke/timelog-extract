"""Tests for `gittan nocfo-invoice` — NoCFO draft invoices from approved hours.

Synthetic data only; every network call is mocked.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from core import (
    cli_nocfo_invoice as cli_mod,
    nocfo_client,
    nocfo_invoice as ni,
    reported_time as rt,
)
from core.cli import app

PROJECTS = [
    {"name": "Kettu Logistics", "nocfo_contact_id": 101, "nocfo_product_id": 7},
    {"name": "Saimaa Studio", "nocfo_contact_id": "202", "nocfo_product_id": "8"},
    {"name": "Side project"},
]


class BuildDraftsTests(unittest.TestCase):
    def setUp(self):
        self.mapping = ni.build_mapping(PROJECTS)

    def test_mapping_needs_contact_and_product(self):
        self.assertEqual(set(self.mapping), {"Kettu Logistics", "Saimaa Studio"})
        self.assertEqual(self.mapping["Saimaa Studio"], ni.NocfoMapping(202, 8))

    def test_one_draft_per_contact_one_row_per_project_day(self):
        approved = {
            ("Kettu Logistics", "2026-11-20"): 3.5,
            ("Kettu Logistics", "2026-11-19"): 2.0,
            ("Saimaa Studio", "2026-11-20"): 1.25,
            ("Side project", "2026-11-20"): 4.0,
            ("Uncategorized", "2026-11-20"): 0.5,
            ("Kettu Logistics", "2026-10-01"): 9.0,  # outside the period
        }
        drafts, unmapped = ni.build_drafts(
            approved, self.mapping, "2026-11-16", "2026-11-22", invoicing_date="2026-11-23"
        )
        self.assertEqual([d.contact_id for d in drafts], [101, 202])
        kettu = drafts[0]
        self.assertEqual(kettu.total_hours, 5.5)
        self.assertEqual([r.day for r, _ in kettu.rows], ["2026-11-19", "2026-11-20"])
        self.assertEqual(unmapped, {"Side project": 4.0, "Uncategorized": 0.5})

    def test_payload_is_draft_shaped_and_has_no_status_or_money(self):
        drafts, _ = ni.build_drafts(
            {("Kettu Logistics", "2026-11-20"): 3.5}, self.mapping,
            "2026-11-20", "2026-11-20", invoicing_date="2026-11-23",
        )
        body = drafts[0].payload()
        self.assertEqual(body["receiver"], 101)
        self.assertEqual(body["invoicing_date"], "2026-11-23")
        self.assertNotIn("status", body)
        self.assertEqual(body["rows"], [{
            ni.ROW_PRODUCT_FIELD: 7,
            ni.ROW_QUANTITY_FIELD: 3.5,
            ni.ROW_DESCRIPTION_FIELD: "2026-11-20 · Kettu Logistics",
        }])

    def test_project_filter(self):
        drafts, _ = ni.build_drafts(
            {("Kettu Logistics", "2026-11-20"): 1.0, ("Saimaa Studio", "2026-11-20"): 1.0},
            self.mapping, "2026-11-20", "2026-11-20", project_filter="Saimaa Studio",
        )
        self.assertEqual([d.contact_id for d in drafts], [202])


class ClientTests(unittest.TestCase):
    def test_credentials_from_env_and_repr_hides_token(self):
        with patch.dict(os.environ, {"NOCFO_API_TOKEN": "secret-token", "NOCFO_BUSINESS": "demo-oy"}):
            creds = nocfo_client.resolve_nocfo_credentials()
        self.assertEqual(creds.business, "demo-oy")
        self.assertEqual(creds.base_url, nocfo_client.DEFAULT_BASE_URL)
        self.assertNotIn("secret-token", repr(creds))

    def test_missing_business_means_no_credentials(self):
        with patch.dict(os.environ, {"NOCFO_API_TOKEN": "t"}, clear=True):
            self.assertIsNone(nocfo_client.resolve_nocfo_credentials())

    def test_refuses_payload_that_sets_status(self):
        creds = nocfo_client.NocfoCredentials("t", "demo-oy")
        with self.assertRaises(ValueError):
            nocfo_client.create_draft_invoice(creds, {"status": "ACCEPTED"})

    def test_create_posts_to_draft_endpoint_with_token_header(self):
        creds = nocfo_client.NocfoCredentials("t0k", "demo-oy")
        with patch.object(nocfo_client, "_request", return_value={"id": 55, "status": "DRAFT"}) as req:
            out = nocfo_client.create_draft_invoice(creds, {"receiver": 1, "rows": []})
        self.assertEqual(out["id"], 55)
        req.assert_called_once_with(creds, "POST", "/v1/invoicing/demo-oy/invoice/", {"receiver": 1, "rows": []})

    def test_client_has_no_accept_or_send_calls(self):
        public = {name for name in dir(nocfo_client) if not name.startswith("_")}
        self.assertFalse({n for n in public if "accept" in n or "send" in n})


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.config = base / "timelog_projects.json"
        self.config.write_text(json.dumps({"projects": PROJECTS}), encoding="utf-8")
        self.patches = [
            patch.object(rt, "reported_base_dir", return_value=base / "reported"),
            patch.object(ni, "oplog_path", return_value=base / "nocfo_oplog.jsonl"),
            patch.dict(os.environ, {"NOCFO_API_TOKEN": "t", "NOCFO_BUSINESS": "demo-oy"}),
        ]
        for p in self.patches:
            p.start()
        rt.append_record(rt.ReportedTimeRecord(
            date="2026-11-20", project="Kettu Logistics", hours=3.5,
            source="manual", state="confirmed", note="synthetic",
        ))
        rt.append_record(rt.ReportedTimeRecord(
            date="2026-11-20", project="Saimaa Studio", hours=2.0,
            source="manual", state="proposed", note="not approved yet",
        ))

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _run(self, *extra, input=None):
        return CliRunner().invoke(app, [
            "nocfo-invoice", "--from", "2026-11-16", "--to", "2026-11-22",
            "--projects-config", str(self.config), *extra,
        ], input=input)

    def test_dry_run_prints_payload_and_never_calls_network(self):
        with patch.object(cli_mod, "create_draft_invoice") as create:
            result = self._run("--dry-run")
        self.assertEqual(result.exit_code, 0, msg=result.output)
        create.assert_not_called()
        self.assertIn('"receiver": 101', result.output)
        self.assertIn("nothing was sent", result.output)
        # proposed (unapproved) time never reaches an invoice
        self.assertNotIn('"receiver": 202', result.output)

    def test_declining_confirmation_creates_nothing(self):
        with patch.object(cli_mod, "create_draft_invoice") as create:
            result = self._run(input="n\n")
        self.assertEqual(result.exit_code, 0, msg=result.output)
        create.assert_not_called()
        self.assertIn("created=0, skipped=1", result.output)

    def test_confirmed_run_creates_draft_and_second_run_skips(self):
        with patch.object(cli_mod, "create_draft_invoice", return_value={"id": 900, "status": "DRAFT"}) as create:
            first = self._run(input="y\n")
            second = self._run(input="y\n")
        self.assertEqual(first.exit_code, 0, msg=first.output)
        self.assertIn("draft invoice id=900", first.output)
        self.assertEqual(create.call_count, 1)
        self.assertIn("already created", second.output)

    def test_missing_credentials_fails_cleanly(self):
        with patch.dict(os.environ, {}, clear=True):
            result = self._run(input="y\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("NOCFO_API_TOKEN", result.output)


if __name__ == "__main__":
    unittest.main()
