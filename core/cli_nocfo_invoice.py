"""`gittan nocfo-invoice` — create NoCFO sales-invoice DRAFTS from approved hours.

Gittan proposes, the user approves, NoCFO does the accounting:

- only confirmed/edited reported time is used (``gittan reported review`` first);
- ``--dry-run`` previews the rows offline and makes no network call;
- a real run reads the NoCFO products, prints the exact payload, then asks;
- every draft needs an interactive yes (default No);
- the invoice is created in NoCFO's DRAFT state; accepting and sending it is
  done by a human inside NoCFO. Gittan has no accept/send call at all.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.config import default_projects_config_option, load_projects_config_payload
from core.nocfo_client import (
    ENV_BUSINESS,
    ENV_TOKEN,
    NocfoHttpError,
    create_draft_invoice,
    get_product,
    resolve_nocfo_credentials,
)
from core.nocfo_invoice import (
    DEFAULT_PAYMENT_DAYS,
    PRODUCT_ROW_FIELDS,
    NocfoOplogError,
    NocfoOpRow,
    blocking_markers,
    build_drafts,
    build_mapping,
    payload_hash,
    record_op,
)
from core.reported_time import reported_hours_by_project_day


def _print_draft(draft) -> None:
    typer.echo(
        f"Draft for NoCFO contact {draft.contact_id}: {len(draft.rows)} row(s), "
        f"{draft.total_hours:.2f} h ({draft.date_from} – {draft.date_to})"
    )
    for row, _product in draft.rows:
        typer.echo(f"  {row.day}  {row.project}  {row.hours:.2f} h")


def _placeholder_products(drafts) -> dict:
    """Offline stand-ins for the product fields a real run reads from NoCFO."""
    ids = {pid for d in drafts for pid in d.product_ids}
    return {
        pid: {key: f"<from NoCFO product {pid}>" for key in (*PRODUCT_ROW_FIELDS, "vat_exclusive_amount")}
        for pid in ids
    }


def _blocking_or_exit(business: str) -> dict:
    try:
        return blocking_markers(business)
    except NocfoOplogError as exc:
        raise typer.BadParameter(str(exc))


def _skip_reason(prior) -> str:
    if prior.status == "pending":
        return (f"Skipped: an earlier attempt on {prior.created_at} did not finish, so a draft may "
                "exist in NoCFO. Check NoCFO, then use --force-new if there is none.")
    return (f"Skipped: draft {prior.invoice_id} already created for this contact and period "
            f"on {prior.created_at}. Use --force-new to create another.")


@app.command("nocfo-invoice")
def nocfo_invoice(
    date_from: Annotated[datetime, typer.Option("--from", formats=["%Y-%m-%d"], help="First day of the billing period (YYYY-MM-DD)")],
    date_to: Annotated[datetime, typer.Option("--to", formats=["%Y-%m-%d"], help="Last day of the billing period (YYYY-MM-DD)")],
    project: Annotated[Optional[str], typer.Option(help="Only invoice this project")] = None,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    payment_days: Annotated[int, typer.Option("--payment-days", min=0, help="Payment term in days")] = DEFAULT_PAYMENT_DAYS,
    dry_run: Annotated[bool, typer.Option(help="Preview offline; no network call")] = False,
    force_new: Annotated[bool, typer.Option("--force-new", help="Create a draft even if one exists (or may exist) for this contact and period")] = False,
    nocfo_api_token: Annotated[Optional[str], typer.Option(help=f"NoCFO personal API token (default: ${ENV_TOKEN})")] = None,
    nocfo_business: Annotated[Optional[str], typer.Option(help=f"NoCFO business slug (default: ${ENV_BUSINESS})")] = None,
):
    """Create NoCFO sales-invoice DRAFTS from approved (confirmed) hours. Never accepts or sends."""
    start, end = date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")
    if start > end:
        raise typer.BadParameter("--from must be on or before --to")

    payload = load_projects_config_payload(Path(projects_config).expanduser())
    mapping = build_mapping(payload.get("projects", []))
    approved = reported_hours_by_project_day()
    drafts, unmapped = build_drafts(approved, mapping, start, end, project_filter=project)

    for name, hours in sorted(unmapped.items()):
        typer.echo(f"Not invoiced (no nocfo_contact_id/nocfo_product_id): {name} {hours:.2f} h")
    if not drafts:
        typer.echo("No approved hours to invoice in this period.")
        typer.echo("Next: approve hours with `gittan reported review`, and map projects with "
                   "`nocfo_contact_id` + `nocfo_product_id` in timelog_projects.json.")
        return

    if dry_run:
        placeholders = _placeholder_products(drafts)
        for draft in drafts:
            _print_draft(draft)
            typer.echo(json.dumps(draft.payload(placeholders, payment_days), indent=2, ensure_ascii=False))
        typer.echo("Dry run: nothing was sent to NoCFO. A real run reads name, unit, price and VAT "
                   "from each NoCFO product and shows the exact payload before asking.")
        return

    creds = resolve_nocfo_credentials(nocfo_api_token, nocfo_business)
    if creds is None:
        raise typer.BadParameter(f"Missing NoCFO credentials: set {ENV_TOKEN} and {ENV_BUSINESS}")

    seen = _blocking_or_exit(creds.business)
    # Only read products for drafts that can still be created, so a deleted
    # product behind an already-invoiced period cannot block the others.
    to_create = [d for d in drafts if force_new or d.marker not in seen]
    products = {}
    for pid in sorted({pid for d in to_create for pid in d.product_ids}):
        try:
            products[pid] = get_product(creds, pid)
        except Exception as exc:  # noqa: BLE001 - read failure: nothing was written
            raise typer.BadParameter(f"Could not read NoCFO product {pid}: {exc}")

    created = skipped = failed = 0
    for draft in drafts:
        _print_draft(draft)
        prior = seen.get(draft.marker)
        if prior and not force_new:
            typer.echo(_skip_reason(prior))
            skipped += 1
            continue
        body = draft.payload(products, payment_days)
        typer.echo(json.dumps(body, indent=2, ensure_ascii=False))
        if not typer.confirm("Create this invoice as a DRAFT in NoCFO?", default=False):
            skipped += 1
            continue
        # Re-read after the (possibly long) prompt: another run may have created
        # this draft meanwhile. Single-user CLI, so a re-check right before the
        # POST is the guard; no cross-process lock.
        prior = _blocking_or_exit(creds.business).get(draft.marker)
        if prior and not force_new:
            typer.echo(_skip_reason(prior))
            skipped += 1
            continue

        body_hash = payload_hash(body)
        # Retrying an unfinished attempt with the same body reuses its key, so
        # NoCFO replays the first draft (within 24 h) instead of creating another.
        if prior and prior.status == "pending" and prior.payload_hash == body_hash and prior.idempotency_key:
            key = prior.idempotency_key
        else:
            key = str(uuid.uuid4())

        def op(status: str, invoice_id: str = "") -> NocfoOpRow:
            return NocfoOpRow(
                marker=draft.marker, business=creds.business, invoice_id=invoice_id,
                contact_id=draft.contact_id, status=status,
                total_hours=draft.total_hours, payload_hash=body_hash, idempotency_key=key,
            )

        try:
            record_op(op("pending"))  # durable before the POST, so a lost response still blocks a repeat
        except OSError as exc:
            raise typer.BadParameter(f"Could not write the local NoCFO op-log ({exc}); nothing was sent.")
        try:
            response = create_draft_invoice(creds, body, idempotency_key=key)
        except NocfoHttpError as exc:
            failed += 1
            if exc.definitely_not_created:
                record_op(op("rejected"))
                typer.echo(f"Failed (NoCFO rejected it, nothing created): {exc}")
            else:
                typer.echo(f"Failed with an unknown outcome: {exc}. A draft may exist in NoCFO; "
                           "check there before re-running (then use --force-new if there is none).")
            continue
        except Exception as exc:  # noqa: BLE001 - outcome unknown: keep it pending
            failed += 1
            typer.echo(f"Failed with an unknown outcome: {exc}. A draft may exist in NoCFO; "
                       "check there before re-running (then use --force-new if there is none).")
            continue
        invoice_id = str(response.get("id"))
        created += 1
        typer.echo(f"Created NoCFO draft invoice id={invoice_id} (status {response.get('status', 'DRAFT')}).")
        try:
            record_op(op("created", invoice_id))
        except OSError as exc:
            typer.echo(f"Warning: could not record draft {invoice_id} in the local op-log ({exc}); "
                       "it stays marked pending, so this period is still protected from a repeat.")

    typer.echo(f"NoCFO summary: created={created}, skipped={skipped}, failed={failed}")
    if created:
        typer.echo("Next: open the draft in NoCFO, check rows and VAT, then accept and send it there.")
