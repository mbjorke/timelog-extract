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

    profiles, _cfg, _ws = load_profiles(
        projects_config, SimpleNamespace(project="", keywords="", email="")
    )
    names = [n.strip() for n in (calendar_names or "").split(",") if n.strip()]

    try:
        rows = read_calendar_titles(Path.home(), dt_from, dt_to, names or None)
    except RuntimeError as exc:
        raise SystemExit(
            f"Cannot read Calendar: {exc}. "
            "Grant Full Disk Access and verify with `gittan doctor` (Calendar row)."
        )

    suggestions = suggest_projects_from_titles(
        [summary for _cal, summary in rows], profiles, min_count=min_count
    )

    if output_format == "json":
        print(json.dumps([s.as_json_dict() for s in suggestions], ensure_ascii=False, indent=2))
        return

    scope = ", ".join(names) if names else "all calendars"
    print(f"Scanned {len(rows)} calendar event(s) ({scope}, {from_str} .. {to_str or 'today'}).")
    if not suggestions:
        print("No new project codes found (everything seen is already covered, or no distinctive codes).")
        return

    print(f"\nSuggested projects (codes not yet in your config), min {min_count} occurrence(s):\n")
    print(f"  {'code':<22} {'events':>6}  example")
    print(f"  {'-'*22} {'-'*6}  {'-'*30}")
    for s in suggestions:
        example = (s.examples[0] if s.examples else "")[:40]
        print(f"  {s.code:<22} {s.count:>6}  {example}")

    profiles_stub = {"projects": [s.as_profile() for s in suggestions]}
    print("\nTo use, add these to your projects config (review names/terms first):\n")
    print(json.dumps(profiles_stub, ensure_ascii=False, indent=2))
    print("\nNote: heuristic suggestions — rename projects and merge related codes as needed.")
