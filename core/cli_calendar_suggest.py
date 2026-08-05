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
from typing import Annotated, Optional

import typer
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table

from collectors.calendar import read_calendar_titles
from core.analytics import get_date_range
from core.calendar_suggest import suggest_projects_from_titles
from core.cli_app import app
from core.config import default_projects_config_option, normalize_profile
from outputs.terminal_theme import (
    CLR_VALUE_ORANGE,
    STYLE_BORDER,
    STYLE_DIM,
    STYLE_LABEL,
    STYLE_MUTED,
)

_LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc


def _configured_profiles(projects_config: str) -> list[dict]:
    """Parse projects config file directly to avoid fallbacks."""
    path = Path(projects_config).expanduser()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            raw = data.get("projects", [])
        else:
            return []
    except Exception:
        return []

    profiles: list[dict] = []
    for p in raw:
        if isinstance(p, dict) and p.get("enabled", True):
            try:
                profiles.append(normalize_profile(p))
            except Exception:
                # Skip individual malformed profiles (e.g. missing 'name') so
                # we don't discard the entire valid projects list.
                continue
    return profiles


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

    profiles = _configured_profiles(projects_config)
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

    console = Console()

    # Escape user calendar names and event details to prevent Rich from misinterpreting
    # bracketed characters (like '[bold]' or '[/]') as markup tags.
    scope = escape(", ".join(names) if names else "all calendars")
    console.print(
        f"Scanned [bold {STYLE_LABEL}]{len(rows)}[/bold {STYLE_LABEL}] calendar event(s) "
        f"({scope}, {from_str} .. {to_str or 'today'})."
    )
    if not suggestions:
        console.print(
            f"[{CLR_VALUE_ORANGE}]No new project codes found[/{CLR_VALUE_ORANGE}] "
            f"[{STYLE_MUTED}](everything seen is already covered, or no distinctive codes).[/{STYLE_MUTED}]"
        )
        return

    console.print(
        f"\n[bold {STYLE_LABEL}]Suggested projects[/bold {STYLE_LABEL}] "
        f"[{STYLE_MUTED}](codes not yet in your config, min {min_count} occurrence(s)):[/{STYLE_MUTED}]\n"
    )

    table = Table(
        box=box.ROUNDED,
        border_style=STYLE_BORDER,
        header_style=f"bold {STYLE_LABEL}",
    )
    table.add_column("Code", style=CLR_VALUE_ORANGE)
    table.add_column("Events", justify="right", style=STYLE_MUTED)
    table.add_column("Example", style=STYLE_DIM)

    for s in suggestions:
        example = (s.examples[0] if s.examples else "")[:40]
        table.add_row(escape(s.code), str(s.count), escape(example))

    console.print(table)

    profiles_stub = {"projects": [s.as_profile() for s in suggestions]}
    console.print(
        f"\n[bold {STYLE_LABEL}]To use, add these to your projects config[/bold {STYLE_LABEL}] "
        f"[{STYLE_MUTED}](review names/terms first):[/{STYLE_MUTED}]\n"
    )
    json_str = json.dumps(profiles_stub, ensure_ascii=False, indent=2)
    syntax = Syntax(json_str, "json", theme="ansi", background_color="default")
    console.print(syntax)
    console.print(
        f"\n[{STYLE_DIM}]Note: heuristic suggestions — rename projects and merge related codes as needed.[/{STYLE_DIM}]"
    )
    console.print(
        f"[{STYLE_MUTED}]Next: edit your config to add the suggested project(s), or run `gittan setup` to map local folders.[/{STYLE_MUTED}]"
    )
    console.print(
        f"[{STYLE_MUTED}]Docs: see `docs/runbooks/calendar-time-report-onboarding.md` to map suggested projects to local folders.[/{STYLE_MUTED}]"
    )
