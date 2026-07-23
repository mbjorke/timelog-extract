"""Typer command: evidence — health and data controls for the shadow log."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from core.cli_app import app


@app.command("evidence")
def evidence(
    export: Annotated[Optional[str], typer.Option("--export", help="Write all stored evidence to a JSONL file at PATH, then exit.")] = None,
    erase: Annotated[bool, typer.Option("--erase", help="Delete the entire local evidence store (asks to confirm unless --yes).")] = False,
    prune_older_than: Annotated[Optional[int], typer.Option("--prune-older-than", help="Drop records older than N days and re-link the hash chain, then exit.")] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation prompt for --erase.")] = False,
) -> None:
    """Show shadow-log health, or manage your local evidence (export / erase / prune).

    With no options this is read-only health. Capture is enabled via
    `gittan report --shadow-log on` or `gittan status --shadow-log on`.
    """
    from rich.console import Console

    from core import evidence_store
    from core.evidence_store import store_health
    from outputs.terminal_theme import (
        CLR_GREEN,
        CLR_VALUE_ORANGE,
        FAIL_ICON,
        STYLE_LABEL,
        STYLE_MUTED,
    )

    console = Console()

    data_controls = sum([export is not None, prune_older_than is not None, erase])
    if data_controls > 1:
        console.print(
            f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: --export, --prune-older-than, and --erase are mutually exclusive.[/]"
        )
        console.print(
            f"[{STYLE_MUTED}]Next: use only one of these data control options.[/]"
        )
        raise typer.Exit(code=1)

    if export is not None:
        result = evidence_store.export_store(export)
        msg = f"Exported {result['records']} record(s) → {result['path']}"
        if result["records"] == 0:
            msg += f" [{STYLE_MUTED}](store is empty)[/]"
        console.print(msg)
        return
    if prune_older_than is not None:
        try:
            result = evidence_store.prune_older_than(prune_older_than)
        except ValueError as exc:
            console.print(f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: {exc}[/]")
            raise typer.Exit(code=1) from exc
        console.print(f"Pruned {result.get('removed', 0)} record(s); {result.get('kept', 0)} kept.")
        return
    if erase:
        if not yes and not typer.confirm("Permanently delete the local evidence store?"):
            console.print(f"[{STYLE_MUTED}]Aborted.[/{STYLE_MUTED}]")
            return
        result = evidence_store.erase_store()
        console.print("Evidence store erased." if result["removed"] else f"[{STYLE_MUTED}]No store to erase.[/{STYLE_MUTED}]")
        return

    health = store_health()
    if not health.get("enabled"):
        console.print(
            f"[{STYLE_MUTED}]Shadow log: off — no store at {health['base_dir']}. "
            f"Enable with `gittan report --shadow-log on` or `gittan status --shadow-log on`.[/{STYLE_MUTED}]"
        )
        return

    console.print(f"[bold {STYLE_LABEL}]Evidence shadow log[/bold {STYLE_LABEL}] — {health['base_dir']}")
    console.print(
        f"Records: [{CLR_VALUE_ORANGE}]{health['total_records']}[/{CLR_VALUE_ORANGE}] "
        f"(captured today: {health['records_captured_today']})"
    )
    console.print(f"Last capture: {health['last_captured_at'] or '—'}")
    console.print(f"Retention span: {health['retention_span'] or '—'}")
    if health["chain_ok"]:
        console.print(f"Chain integrity: [{CLR_GREEN}]OK[/]")
    else:
        console.print(f"Chain integrity: {FAIL_ICON} [{CLR_VALUE_ORANGE}]BROKEN[/] ([{STYLE_MUTED}]{len(health['chain_breaks'])} issue(s)[/])")
        for issue in health["chain_breaks"][:5]:
            console.print(f"[{CLR_VALUE_ORANGE}]  - {issue}[/]")
    for source, count in health["per_source"].items():
        console.print(f"[{STYLE_MUTED}]  {source}: {count}[/{STYLE_MUTED}]")
