"""`gittan nocfo-invoice` — create NoCFO sales-invoice DRAFTS from approved hours.

Gittan proposes, the user approves, NoCFO does the accounting:

- only confirmed/edited reported time is used (``gittan reported review`` first);
- ``--dry-run`` prints the exact payload and makes no network call;
- every draft needs an interactive yes (default No);
- the invoice is created in NoCFO's DRAFT state; accepting and sending it is
  done by a human inside NoCFO. Gittan has no accept/send call at all.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.config import default_projects_config_option, load_projects_config_payload
from core.nocfo_client import (
    ENV_BUSINESS,
    ENV_TOKEN,
    create_draft_invoice,
    resolve_nocfo_credentials,
)
from core.nocfo_invoice import (
    NocfoOplogError,
    NocfoOpRow,
    build_drafts,
    build_mapping,
    existing_markers,
    payload_hash,
    record_draft,
)
from core.reported_time import reported_hours_by_project_day


def _print_draft(draft) -> None:
    typer.echo(
        f"Draft for NoCFO contact {draft.contact_id}: {len(draft.rows)} row(s), "
        f"{draft.total_hours:.2f} h ({draft.date_from} – {draft.date_to})"
    )
    for row, _product in draft.rows:
        typer.echo(f"  {row.day}  {row.project}  {row.hours:.2f} h")


@app.command("nocfo-invoice")
def nocfo_invoice(
    date_from: Annotated[datetime, typer.Option("--from", formats=["%Y-%m-%d"], help="First day of the billing period (YYYY-MM-DD)")],
    date_to: Annotated[datetime, typer.Option("--to", formats=["%Y-%m-%d"], help="Last day of the billing period (YYYY-MM-DD)")],
    project: Annotated[Optional[str], typer.Option(help="Only invoice this project")] = None,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    dry_run: Annotated[bool, typer.Option(help="Print the exact payload; no network call")] = False,
    force_new: Annotated[bool, typer.Option("--force-new", help="Create a draft even if one was already created for this contact and period")] = False,
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
        for draft in drafts:
            _print_draft(draft)
            typer.echo(json.dumps(draft.payload(), indent=2, ensure_ascii=False))
        typer.echo("Dry run: nothing was sent to NoCFO.")
        return

    creds = resolve_nocfo_credentials(nocfo_api_token, nocfo_business)
    if creds is None:
        raise typer.BadParameter(f"Missing NoCFO credentials: set {ENV_TOKEN} and {ENV_BUSINESS}")

    try:
        seen = existing_markers(creds.business)
    except NocfoOplogError as exc:
        raise typer.BadParameter(str(exc))
    created = skipped = failed = 0
    for draft in drafts:
        _print_draft(draft)
        prior = seen.get(draft.marker)
        if prior and not force_new:
            typer.echo(f"Skipped: draft {prior.invoice_id} already created for this contact and period "
                       f"on {prior.created_at}. Use --force-new to create another.")
            skipped += 1
            continue
        if not typer.confirm("Create this invoice as a DRAFT in NoCFO?", default=False):
            skipped += 1
            continue
        # Re-read after the (possibly long) prompt: another run may have created
        # this draft meanwhile. Gittan is a single-user CLI, so a re-check right
        # before the POST is the guard; no cross-process lock.
        if not force_new and draft.marker in existing_markers(creds.business):
            typer.echo("Skipped: another run created this draft while you were confirming.")
            skipped += 1
            continue
        body = draft.payload()
        try:
            response = create_draft_invoice(creds, body)
        except Exception as exc:  # noqa: BLE001 - surface every failure, keep going
            failed += 1
            typer.echo(f"Failed: {exc}")
            continue
        invoice_id = str(response.get("id"))
        created += 1
        typer.echo(f"Created NoCFO draft invoice id={invoice_id} (status {response.get('status', 'DRAFT')}).")
        try:
            record_draft(NocfoOpRow(
                marker=draft.marker,
                business=creds.business,
                invoice_id=invoice_id,
                contact_id=draft.contact_id,
                total_hours=draft.total_hours,
                payload_hash=payload_hash(body),
            ))
        except OSError as exc:
            typer.echo(f"Warning: could not write the local NoCFO op-log ({exc}).")

    typer.echo(f"NoCFO summary: created={created}, skipped={skipped}, failed={failed}")
    if created:
        typer.echo("Next: open the draft in NoCFO, check rows and VAT, then accept and send it there.")
