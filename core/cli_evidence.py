"""Typer command: evidence — read-only health of the local evidence shadow log."""

from __future__ import annotations

import typer

from core.cli_app import app


@app.command("evidence")
def evidence() -> None:
    """Show local evidence shadow-log health (read-only; writes nothing).

    Reports whether the opt-in store exists, how many records it holds, today's
    captures, the retention span, and tamper-evident hash-chain integrity.
    Enable capture with `gittan report --shadow-log on` or `gittan status --shadow-log on`.
    """
    from rich.console import Console

    from core.evidence_store import store_health
    from outputs.terminal_theme import (
        CLR_GREEN,
        CLR_VALUE_ORANGE,
        STYLE_LABEL,
        STYLE_MUTED,
    )

    console = Console()
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
        console.print(f"Chain integrity: [{CLR_GREEN}]OK[/{CLR_GREEN}]")
    else:
        console.print(f"Chain integrity: [red]BROKEN[/red] ({len(health['chain_breaks'])} issue(s))")
        for issue in health["chain_breaks"][:5]:
            console.print(f"[red]  - {issue}[/red]")
    for source, count in health["per_source"].items():
        console.print(f"[{STYLE_MUTED}]  {source}: {count}[/{STYLE_MUTED}]")
