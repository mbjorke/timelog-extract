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

# Synthetic NoCFO product record (shape from NoCFO's OpenAPI Product schema).
PRODUCT = {
    "id": 7, "name": "Consulting", "unit": "h", "amount": 119.23, "is_vat_inclusive": True,
    "vat_exclusive_amount": 95.0, "vat_inclusive_amount": 119.23, "vat_rate": 25.5, "vat_code": 1,
}

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

    def test_payload_hours_are_quantity_and_price_comes_from_product(self):
        drafts, _ = ni.build_drafts(
            {("Kettu Logistics", "2026-11-20"): 3.5}, self.mapping,
            "2026-11-20", "2026-11-20", invoicing_date="2026-11-23",
        )
        body = drafts[0].payload({7: PRODUCT}, payment_condition_days=21)
        self.assertEqual(body["receiver"], 101)
        self.assertEqual(body["invoicing_date"], "2026-11-23")
        self.assertEqual(body["payment_condition_days"], 21)
        self.assertNotIn("status", body)
        self.assertEqual(body["rows"], [{
            "name": "Consulting", "unit": "h", "vat_rate": 25.5, "vat_code": 1,
            "amount": 95.0,  # VAT-exclusive unit price from the product, not the hours
            "product": 7,
            "product_count": 3.5,
            "description": "2026-11-20 · Kettu Logistics",
        }])

    def test_project_filter(self):
        drafts, _ = ni.build_drafts(
            {("Kettu Logistics", "2026-11-20"): 1.0, ("Saimaa Studio", "2026-11-20"): 1.0},
            self.mapping, "2026-11-20", "2026-11-20", project_filter="Saimaa Studio",
        )
        self.assertEqual([d.contact_id for d in drafts], [202])


class ClientTests(unittest.TestCase):
    def test_credentials_from_env_and_repr_hides_token(self):
        env = {"NOCFO_API_TOKEN": "secret-token", "NOCFO_BUSINESS": "demo-oy"}
        with patch.dict(os.environ, env, clear=True):
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
        req.assert_called_once_with(creds, "POST", "/v1/invoicing/demo-oy/invoice/", {"receiver": 1, "rows": []}, None)

    def test_create_sends_idempotency_key_header(self):
        creds = nocfo_client.NocfoCredentials("t0k", "demo-oy")
        with patch.object(nocfo_client, "_request", return_value={"id": 55}) as req:
            nocfo_client.create_draft_invoice(creds, {"receiver": 1}, idempotency_key="k-1")
        self.assertEqual(req.call_args.args[4], {"Idempotency-Key": "k-1"})

    def test_only_refusing_4xx_counts_as_not_created(self):
        verdict = {code: nocfo_client.NocfoHttpError("x", code).definitely_not_created
                   for code in (400, 401, 403, 404, 408, 409, 422, 429, 500, 502, 504)}
        self.assertEqual({c for c, v in verdict.items() if v}, {400, 401, 403, 404, 422, 429})

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
            patch.object(cli_mod, "get_product", return_value=PRODUCT),
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
        self.assertIn('"product_count": 3.5', result.output)
        self.assertIn("<from NoCFO product 7>", result.output)
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
        self.assertIn('"amount": 95.0', first.output)  # exact payload shown before the prompt
        self.assertEqual(create.call_count, 1)
        self.assertIn("already created", second.output)
        statuses = [op.status for op in ni.load_ops()]
        self.assertEqual(statuses, ["pending", "created"])

    def test_unknown_outcome_stays_pending_and_blocks_repeat(self):
        with patch.object(cli_mod, "create_draft_invoice", side_effect=TimeoutError("read timed out")) as create:
            first = self._run(input="y\n")
            second = self._run(input="y\n")
        self.assertIn("unknown outcome", first.output)
        self.assertEqual(create.call_count, 1)
        self.assertIn("did not finish", second.output)

    def test_server_error_stays_pending_and_blocks_repeat(self):
        gateway = nocfo_client.NocfoHttpError("HTTP 502 bad gateway", 502)
        with patch.object(cli_mod, "create_draft_invoice", side_effect=gateway) as create:
            first = self._run(input="y\n")
            second = self._run(input="y\n")
        self.assertIn("unknown outcome", first.output)
        self.assertEqual(create.call_count, 1)
        self.assertIn("did not finish", second.output)

    def test_force_new_after_unknown_outcome_reuses_idempotency_key(self):
        with patch.object(cli_mod, "create_draft_invoice", side_effect=[TimeoutError("t"), {"id": 902}]) as create:
            self._run(input="y\n")
            retry = self._run("--force-new", input="y\n")
        self.assertIn("draft invoice id=902", retry.output)
        keys = [c.kwargs["idempotency_key"] for c in create.call_args_list]
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], keys[1])

    def test_definite_rejection_allows_retry(self):
        rejected = nocfo_client.NocfoHttpError("HTTP 400 bad row", 400)
        with patch.object(cli_mod, "create_draft_invoice", side_effect=[rejected, {"id": 901}]) as create:
            first = self._run(input="y\n")
            second = self._run(input="y\n")
        self.assertIn("rejected it", first.output)
        self.assertEqual(create.call_count, 2)
        self.assertIn("draft invoice id=901", second.output)

    def test_missing_credentials_fails_cleanly(self):
        with patch.dict(os.environ, {}, clear=True):
            result = self._run(input="y\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("NOCFO_API_TOKEN", result.output)

    def test_damaged_oplog_stops_creation(self):
        ni.oplog_path().write_text("{not json\n", encoding="utf-8")
        with patch.object(cli_mod, "create_draft_invoice") as create:
            result = self._run(input="y\n")
        self.assertNotEqual(result.exit_code, 0)
        create.assert_not_called()
        self.assertIn("unreadable line", result.output)

    def test_draft_created_by_another_run_during_prompt_is_skipped(self):
        def other_run_logs_first(*_args, **_kwargs):
            ni.record_op(ni.NocfoOpRow(
                marker="gittan:101:2026-11-16:2026-11-22", business="demo-oy",
                invoice_id="1", contact_id=101, status="created", total_hours=3.5, payload_hash="x",
            ))
            return True

        with patch.object(cli_mod.typer, "confirm", side_effect=other_run_logs_first), \
                patch.object(cli_mod, "create_draft_invoice") as create:
            result = self._run()
        create.assert_not_called()
        self.assertIn("already created", result.output)


class ProfileNormalizationTests(unittest.TestCase):
    def test_normalize_profile_keeps_nocfo_ids(self):
        from core.config import normalize_profile

        profile = normalize_profile({"name": "Kettu", "nocfo_contact_id": "101", "nocfo_product_id": 7})
        self.assertEqual((profile["nocfo_contact_id"], profile["nocfo_product_id"]), (101, 7))

    def test_normalize_profile_rejects_bad_nocfo_id(self):
        from core.config import normalize_profile

        with self.assertRaises(ValueError):
            normalize_profile({"name": "Kettu", "nocfo_contact_id": True})


if __name__ == "__main__":
    unittest.main()
