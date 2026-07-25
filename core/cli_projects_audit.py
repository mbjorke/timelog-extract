"""Typer command: projects-audit (usage stats)."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from core.anchor_plan import (
    ANCHOR_PLAN_APPLY_MIN_HITS,
    ANCHOR_PLAN_SCHEMA_VERSION,
    build_anchor_plan_from_audit,
)
from core.cli_app import app
from core.cli_date_range import resolve_date_window
from core.cli_options import TimelogRunOptions
from core.config import default_projects_config_option
from core.projects_audit import (
    SIGNAL_KIND_LABELS,
    TRIM_PLAN_SCHEMA_VERSION,
    build_projects_audit_payload,
    build_zero_hit_trim_plan_from_audit,
)
from outputs.terminal_theme import (
    CLR_GREEN,
    CLR_VALUE_ORANGE,
    OK_ICON,
    STYLE_BORDER,
    STYLE_DIM,
    STYLE_LABEL,
    STYLE_MUTED,
    WARN_ICON,
)


def _default_date_window() -> tuple[str, str]:
    end_d = date.today()
    start_d = end_d - timedelta(days=6)
    return start_d.isoformat(), end_d.isoformat()


@app.command("projects-audit")
def projects_audit(
    date_from: Annotated[
        Optional[datetime],
        typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)"),
    ] = None,
    date_to: Annotated[
        Optional[datetime],
        typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)"),
    ] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[
        str, typer.Option(help="JSON config file")
    ] = default_projects_config_option(),
    json_out: Annotated[bool, typer.Option("--json", help="Print audit JSON to stdout")] = False,
    screen_time: Annotated[str, typer.Option(help="Screen time: auto/on/off")] = "auto",
    max_top_hosts: Annotated[
        int,
        typer.Option(
            help="Max rows per kind in top_signals (hosts/dirs/branches/titles; 0 disables)"
        ),
    ] = 30,
    write_trim_plan: Annotated[
        Optional[str],
        typer.Option(
            "--write-trim-plan",
            help=(
                "Write trim-plan JSON (schema v1) to PATH: removals pre-filled with rules that had "
                "zero hits in this audit window only — not proof they are unused elsewhere. "
                "Does not edit the config; review then: projects-trim -i PATH --dry-run."
            ),
        ),
    ] = None,
    write_anchor_plan: Annotated[
        Optional[str],
        typer.Option(
            "--write-anchor-plan",
            help=(
                "Write anchor-plan JSON (schema v1) to PATH: apply candidates for stable "
                "unanchored signals (host → tracked_urls; repo/dir → match_terms) at "
                f"min_hits>={ANCHOR_PLAN_APPLY_MIN_HITS}. branch/label go to inventory only "
                "(use --include-ephemeral-kinds to promote them). Edit project_name to map "
                "to an existing project. Review then: projects-anchor -i PATH --dry-run."
            ),
        ),
    ] = None,
    include_ephemeral_kinds: Annotated[
        bool,
        typer.Option(
            "--include-ephemeral-kinds",
            help=(
                "Include branch/label in apply candidates (default: inventory only). "
                "Ephemeral kinds are session context — prefer attaching repo/dir to an "
                "existing line instead of permanent match_terms."
            ),
        ),
    ] = False,
    min_hits: Annotated[
        int,
        typer.Option(
            "--min-hits",
            help=(
                f"Minimum hits for apply candidates (default {ANCHOR_PLAN_APPLY_MIN_HITS}). "
                "Values below the default print a warning."
            ),
        ),
    ] = ANCHOR_PLAN_APPLY_MIN_HITS,
    unsafe_low_floor: Annotated[
        bool,
        typer.Option(
            "--unsafe-low-floor",
            help=(
                "Shortcut for --min-hits=1 with an explicit warning. Prefer --min-hits "
                "when you need a conscious override."
            ),
        ),
    ] = False,
) -> None:
    """Count match_terms / tracked_urls hits over deduped collector events (read-only)."""
    from rich.console import Console
    from rich.table import Table

    from core.report_service import run_timelog_report

    console = Console()

    df, dt = resolve_date_window(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        prompt_if_missing=False,
    )
    if not df and not dt:
        df, dt = _default_date_window()

    opts = TimelogRunOptions(
        date_from=df,
        date_to=dt,
        projects_config=projects_config,
        quiet=True,
        include_uncategorized=True,
        screen_time=screen_time,
    )
    report = run_timelog_report(projects_config, df, dt, opts)
    payload = build_projects_audit_payload(
        events=report.all_events,
        profiles=report.profiles,
        date_from=df,
        date_to=dt,
        projects_config=projects_config,
        pool="deduped_all_events",
        top_hosts_limit=max(0, int(max_top_hosts)),
    )

    if write_trim_plan:
        plan = build_zero_hit_trim_plan_from_audit(payload)
        out_path = Path(write_trim_plan).expanduser()
        out_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not json_out:
            console.print(
                f"{OK_ICON} [{CLR_GREEN}]Wrote trim plan ({plan['meta']['zero_hit_candidates']} zero-hit candidates) "
                f"to {out_path} (schema v{TRIM_PLAN_SCHEMA_VERSION}).[/{CLR_GREEN}]"
            )
            console.print(
                f"[{STYLE_MUTED}]Next: Review; then `gittan projects-trim -i {out_path} --dry-run`[/{STYLE_MUTED}]"
            )

    if write_anchor_plan:
        floor = 1 if unsafe_low_floor else max(1, int(min_hits))
        if floor < ANCHOR_PLAN_APPLY_MIN_HITS and not json_out:
            console.print(
                f"{WARN_ICON} [{CLR_VALUE_ORANGE}]Warning: min_hits={floor} is below the safe floor "
                f"({ANCHOR_PLAN_APPLY_MIN_HITS}); one-off noise can become permanent "
                f"match_terms.[/{CLR_VALUE_ORANGE}]"
            )
        plan = build_anchor_plan_from_audit(
            payload,
            min_hits=floor,
            include_ephemeral_kinds=include_ephemeral_kinds,
        )
        out_path = Path(write_anchor_plan).expanduser()
        out_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not json_out:
            inv_n = int(plan["meta"].get("inventory_candidates", 0) or 0)
            inv_note = f", {inv_n} inventory (branch/label)" if inv_n else ""
            console.print(
                f"{OK_ICON} [{CLR_GREEN}]Wrote anchor plan ({plan['meta']['anchor_candidates']} apply candidates"
                f"{inv_note}) to {out_path} (schema v{ANCHOR_PLAN_SCHEMA_VERSION}, "
                f"min_hits={plan['meta']['min_hits']}).[/{CLR_GREEN}]"
            )
            console.print(
                f"[{STYLE_MUTED}]Next: Edit project_name to map to existing projects; then "
                f"`gittan projects-anchor -i {out_path} --dry-run`[/{STYLE_MUTED}]"
            )

    if json_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0)

    console.print(
        f"[bold]projects-audit[/bold] schema v{payload['schema_version']} — "
        f"{payload['event_count']} deduped events, {df} → {dt}"
    )
    console.print(f"[{STYLE_DIM}]{payload['hit_definition']}[/{STYLE_DIM}]")
    from rich import box

    table = Table(
        show_header=True,
        box=box.ROUNDED,
        border_style=STYLE_BORDER,
        header_style=f"bold {STYLE_LABEL}",
    )
    table.add_column("Project", style=STYLE_LABEL)
    table.add_column("Rule", style=STYLE_MUTED)
    table.add_column("Hits", justify="right", style=CLR_VALUE_ORANGE)
    for block in payload.get("projects", []):
        pname = str(block.get("name", ""))
        first = True
        for row in block.get("match_terms", []) or []:
            label = f"{pname}" if first else ""
            table.add_row(
                label,
                f"match_terms: {row.get('value', '')}",
                str(row.get("hits", 0)),
            )
            first = False
        for row in block.get("tracked_urls", []) or []:
            label = f"{pname}" if first else ""
            table.add_row(
                label,
                f"tracked_urls: {row.get('value', '')}",
                str(row.get("hits", 0)),
            )
            first = False
        if first:
            table.add_row(pname, "(no rules)", "—")
    console.print(table)
    if int(max_top_hosts) > 0 and payload.get("top_signals"):
        console.print()
        console.print(f"[{STYLE_DIM}]{payload.get('top_signals_note', '')}[/{STYLE_DIM}]")
        st = Table(
            show_header=True,
            box=box.ROUNDED,
            border_style=STYLE_BORDER,
            header_style=f"bold {STYLE_LABEL}",
        )
        st.add_column("Kind", style=STYLE_LABEL)
        st.add_column("Signal", style=STYLE_MUTED)
        st.add_column("Rule", justify="center", style=STYLE_MUTED)
        st.add_column("Hits", justify="right", style=CLR_VALUE_ORANGE)
        st.add_column("Anchored", justify="center", style=STYLE_LABEL)
        for row in payload["top_signals"]:
            st.add_row(
                SIGNAL_KIND_LABELS.get(str(row.get("kind", "")), str(row.get("kind", ""))),
                str(row.get("value", "")),
                str(row.get("rule_type", "")),
                str(row.get("hits", 0)),
                "yes" if row.get("anchored") else "no",
            )
        console.print(st)
    console.print(f"[{STYLE_DIM}]Re-run with --json for machine-readable output.[/{STYLE_DIM}]")


def _load_json_input(path: Optional[str], schema_version: int, kind: str) -> dict[str, Any]:
    raw = (
        Path(path).expanduser().read_text(encoding="utf-8")
        if (path and path != "-")
        else sys.stdin.read()
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{kind} input must be a JSON object")
    version = data.get("schema_version")
    if type(version) is not int or version != schema_version:
        raise ValueError(f"schema_version must be {schema_version}")
    return data
