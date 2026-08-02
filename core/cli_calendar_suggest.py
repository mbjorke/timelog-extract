"""Typer command: suggest project profiles from calendar event titles (P7).

Onboarding helper — scans a calendar's event titles and proposes project
profiles for distinctive codes (e.g. ``HÅ-DAA``, ``KidneySign``) that are not yet
covered by an existing profile's ``match_terms``. Suggestion-only: it never
writes config.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Optional

import typer

from collectors.calendar import read_calendar_titles
from core.analytics import get_date_range
from core.calendar_suggest import suggest_projects_from_titles
from core.cli_app import app
from core.config import default_projects_config_option, load_profiles

_LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc


@app.command("calendar-suggest")
def calendar_suggest(
    calendar_names: Annotated[
        Optional[str],
        typer.Option(help="Calendars to scan, comma-separated (e.g. 'TimeReport,Work'). Default: all calendars."),
    ] = None,
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    days: Annotated[int, typer.Option(help="Lookback window in days when --from is not given")] = 90,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    min_count: Annotated[int, typer.Option(help="Only suggest codes seen at least this many times")] = 2,
    output_format: Annotated[str, typer.Option("--format", help="terminal/json")] = "terminal",
):
    """Suggest project profiles from calendar title codes (read-only; no config written)."""
    from_str = date_from.strftime("%Y-%m-%d") if date_from else (
        (datetime.now(_LOCAL_TZ) - timedelta(days=days)).strftime("%Y-%m-%d")
    )
    to_str = date_to.strftime("%Y-%m-%d") if date_to else None
    dt_from, dt_to = get_date_range(from_str, to_str, _LOCAL_TZ)

    try:
        profiles, _cfg, _ws = load_profiles(
            projects_config, SimpleNamespace(project="", keywords="", email="")
        )
    except ValueError:
        profiles = []
    names = [n.strip() for n in (calendar_names or "").split(",") if n.strip()]

    try:
        rows = read_calendar_titles(Path.home(), dt_from, dt_to, names or None)
    except RuntimeError as exc:
        raise SystemExit(
            f"Cannot read Calendar: {exc}. "
            "Grant Full Disk Access and verify with `gittan doctor` (Calendar row)."
        ) from None

    suggestions = suggest_projects_from_titles(
        [summary for _cal, summary in rows], profiles, min_count=min_count
    )

    if output_format == "json":
        print(json.dumps([s.as_json_dict() for s in suggestions], ensure_ascii=False, indent=2))
        return

    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.markup import escape
    from rich.syntax import Syntax
    from outputs.terminal_theme import (
        STYLE_LABEL,
        STYLE_MUTED,
        STYLE_BORDER,
        CLR_VALUE_ORANGE,
        STYLE_DIM,
    )

    console = Console()

    scope = ", ".join(names) if names else "all calendars"
    console.print(
        f"Scanned [bold {STYLE_LABEL}]{len(rows)}[/bold {STYLE_LABEL}] calendar event(s) "
        f"({scope}, {from_str} .. {to_str or 'today'})."
    )
    if not suggestions:
        console.print(
            f"[{CLR_VALUE_ORANGE}]No new project codes found[/{CLR_VALUE_ORANGE}] (everything seen is already covered, or no distinctive codes)."
        )
        console.print(
            f"[{STYLE_MUTED}]Next: Check your config or widen the scanned window / calendars.[/{STYLE_MUTED}]"
        )
        return

    console.print(
        f"\n[bold {STYLE_LABEL}]Suggested projects[/bold {STYLE_LABEL}] (codes not yet in your config), min {min_count} occurrence(s):\n"
    )

    table = Table(box=box.ROUNDED, border_style=STYLE_BORDER, show_header=True)
    table.add_column("Code", style=CLR_VALUE_ORANGE, header_style=STYLE_LABEL)
    table.add_column("Events", justify="right", style=STYLE_MUTED, header_style=STYLE_LABEL)
    table.add_column("Example Title", style=STYLE_DIM, header_style=STYLE_LABEL)

    for s in suggestions:
        example = (s.examples[0] if s.examples else "")[:40]
        table.add_row(escape(s.code), str(s.count), escape(example))

    console.print(table)

    profiles_stub = {"projects": [s.as_profile() for s in suggestions]}
    console.print(f"\n[{STYLE_MUTED}]To use, add these to your projects config (review names/terms first):[/{STYLE_MUTED}]\n")

    json_str = json.dumps(profiles_stub, ensure_ascii=False, indent=2)
    syntax = Syntax(json_str, "json", theme="ansi", background_color="default")
    console.print(syntax)

    console.print(
        f"\n[{STYLE_MUTED}]Note: heuristic suggestions — rename projects and merge related codes as needed.[/{STYLE_MUTED}]"
    )
    console.print(
        f"[{STYLE_MUTED}]Next: Run `gittan report` once config is updated to re-analyze.[/{STYLE_MUTED}]"
    )
