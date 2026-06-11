"""Typer commands: projects-audit (usage stats), projects-trim (remove rules)."""

from __future__ import annotations

import copy
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from core.cli_app import app
from core.cli_date_range import resolve_date_window
from core.cli_options import TimelogRunOptions
from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    default_projects_config_option,
    load_projects_config_payload,
    remove_rule_from_project,
    save_projects_config_payload,
)
from core.projects_audit import (
    ANCHOR_PLAN_SCHEMA_VERSION,
    TRIM_PLAN_SCHEMA_VERSION,
    build_dir_anchor_plan_from_audit,
    build_projects_audit_payload,
    build_zero_hit_trim_plan_from_audit,
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
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    json_out: Annotated[bool, typer.Option("--json", help="Print audit JSON to stdout")] = False,
    screen_time: Annotated[str, typer.Option(help="Screen time: auto/on/off")] = "auto",
    max_top_hosts: Annotated[
        int,
        typer.Option(help="Max http(s) hosts to list in top_hosts (0 disables)"),
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
                "Write anchor-plan JSON (schema v1) to PATH: match_term additions for unanchored "
                "working directories (top_dirs) seen in this window. project_name defaults to the "
                "directory leaf — edit to map to an existing project. Review then: "
                "projects-anchor -i PATH --dry-run."
            ),
        ),
    ] = None,
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
        out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not json_out:
            console.print(
                f"[dim]Wrote trim plan ({plan['meta']['zero_hit_candidates']} zero-hit candidates) "
                f"to {out_path} (schema v{TRIM_PLAN_SCHEMA_VERSION}). "
                f"Review; then `gittan projects-trim -i {out_path}` --dry-run.[/dim]"
            )

    if write_anchor_plan:
        plan = build_dir_anchor_plan_from_audit(payload)
        out_path = Path(write_anchor_plan).expanduser()
        out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not json_out:
            console.print(
                f"[dim]Wrote anchor plan ({plan['meta']['anchor_candidates']} candidate dirs) "
                f"to {out_path} (schema v{ANCHOR_PLAN_SCHEMA_VERSION}). "
                f"Edit project_name to map to existing projects; then "
                f"`gittan projects-anchor -i {out_path}` --dry-run.[/dim]"
            )

    if json_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0)

    console.print(
        f"[bold]projects-audit[/bold] schema v{payload['schema_version']} — "
        f"{payload['event_count']} deduped events, {df} → {dt}"
    )
    console.print(f"[dim]{payload['hit_definition']}[/dim]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Project")
    table.add_column("Rule")
    table.add_column("Hits", justify="right")
    for block in payload.get("projects", []):
        pname = str(block.get("name", ""))
        first = True
        for row in block.get("match_terms", []) or []:
            label = f"{pname}" if first else ""
            table.add_row(label, f"match_terms: {row.get('value', '')}", str(row.get("hits", 0)))
            first = False
        for row in block.get("tracked_urls", []) or []:
            label = f"{pname}" if first else ""
            table.add_row(label, f"tracked_urls: {row.get('value', '')}", str(row.get("hits", 0)))
            first = False
        if first:
            table.add_row(pname, "(no rules)", "—")
    console.print(table)
    if int(max_top_hosts) > 0 and payload.get("top_hosts"):
        console.print()
        console.print(f"[dim]{payload.get('top_hosts_note', '')}[/dim]")
        ht = Table(show_header=True, header_style="bold")
        ht.add_column("Host")
        ht.add_column("Hits", justify="right")
        ht.add_column("Anchored", justify="center")
        for row in payload["top_hosts"]:
            ht.add_row(
                str(row.get("host", "")),
                str(row.get("hits", 0)),
                "yes" if row.get("anchored") else "no",
            )
        console.print(ht)
    if payload.get("top_dirs"):
        console.print()
        console.print(f"[dim]{payload.get('top_dirs_note', '')}[/dim]")
        dt_table = Table(show_header=True, header_style="bold")
        dt_table.add_column("Directory")
        dt_table.add_column("Hits", justify="right")
        dt_table.add_column("Anchored", justify="center")
        for row in payload["top_dirs"]:
            dt_table.add_row(
                str(row.get("dir", "")),
                str(row.get("hits", 0)),
                "yes" if row.get("anchored") else "no",
            )
        console.print(dt_table)
    console.print("[dim]Re-run with --json for machine-readable output.[/dim]")


def _load_trim_decisions(path: Optional[str]) -> list[dict[str, Any]]:
    if path and path != "-":
        raw = Path(path).expanduser().read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("trim input must be a JSON object")
    if int(data.get("schema_version", 0)) != TRIM_PLAN_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {TRIM_PLAN_SCHEMA_VERSION}")
    removals = data.get("removals")
    if not isinstance(removals, list):
        raise ValueError("'removals' must be an array")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(removals):
        if not isinstance(item, dict):
            raise ValueError(f"removals[{idx}] must be an object")
        pn = str(item.get("project_name", "")).strip()
        rt = str(item.get("rule_type", "")).strip()
        rv = str(item.get("rule_value", "")).strip()
        if not pn or not rt or not rv:
            raise ValueError(f"removals[{idx}]: project_name, rule_type, rule_value required")
        if rt not in {"match_terms", "tracked_urls"}:
            raise ValueError(f"removals[{idx}]: invalid rule_type")
        out.append({"project_name": pn, "rule_type": rt, "rule_value": rv})
    return out


@app.command("projects-trim")
def projects_trim(
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    input_path: Annotated[
        Optional[str],
        typer.Option("-i", "--input", help="JSON file with removals (use - for stdin)"),
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Print planned removals only; no write")] = False,
) -> None:
    """Remove match_terms / tracked_urls entries using an explicit JSON payload."""
    from rich.console import Console

    console = Console()
    try:
        removals = _load_trim_decisions(input_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        console.print(f"[red]Invalid trim input:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not removals:
        console.print("[yellow]No removals in input; nothing to do.[/yellow]")
        raise typer.Exit(code=0)

    cfg_path = Path(projects_config).expanduser()
    base = load_projects_config_payload(cfg_path)
    work = copy.deepcopy(base) if dry_run else base
    preview: list[str] = []
    for item in removals:
        ok = remove_rule_from_project(
            work,
            project_name=item["project_name"],
            rule_type=item["rule_type"],
            rule_value=item["rule_value"],
        )
        preview.append(
            f"{'remove' if ok else 'skip (not found)'}: {item['project_name']} "
            f"{item['rule_type']}={item['rule_value']!r}"
        )

    console.print("\n".join(preview))
    if dry_run:
        console.print("[yellow]Dry run — config not written.[/yellow]")
        raise typer.Exit(code=0)

    backup = backup_projects_config_if_exists(cfg_path)
    if backup:
        console.print(f"[dim]Backup:[/dim] {backup}")
    save_projects_config_payload(cfg_path, work)
    console.print("[green]projects-trim: config updated.[/green]")


def _load_anchor_decisions(path: Optional[str]) -> list[dict[str, Any]]:
    if path and path != "-":
        raw = Path(path).expanduser().read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("anchor input must be a JSON object")
    if int(data.get("schema_version", 0)) != ANCHOR_PLAN_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {ANCHOR_PLAN_SCHEMA_VERSION}")
    additions = data.get("additions")
    if not isinstance(additions, list):
        raise ValueError("'additions' must be an array")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(additions):
        if not isinstance(item, dict):
            raise ValueError(f"additions[{idx}] must be an object")
        pn = str(item.get("project_name", "")).strip()
        rt = str(item.get("rule_type", "match_terms")).strip() or "match_terms"
        rv = str(item.get("rule_value", "")).strip()
        if not pn or not rv:
            raise ValueError(f"additions[{idx}]: project_name and rule_value required")
        if rt != "match_terms":
            raise ValueError(f"additions[{idx}]: only match_terms additions are supported")
        out.append({"project_name": pn, "rule_type": rt, "rule_value": rv})
    return out


@app.command("projects-anchor")
def projects_anchor(
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    input_path: Annotated[
        Optional[str],
        typer.Option("-i", "--input", help="JSON file with additions (use - for stdin)"),
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Print planned additions only; no write")] = False,
) -> None:
    """Add match_terms to projects from an anchor plan (e.g. unanchored directories)."""
    from rich.console import Console

    console = Console()
    try:
        additions = _load_anchor_decisions(input_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        console.print(f"[red]Invalid anchor input:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not additions:
        console.print("[yellow]No additions in input; nothing to do.[/yellow]")
        raise typer.Exit(code=0)

    cfg_path = Path(projects_config).expanduser()
    base = load_projects_config_payload(cfg_path)
    work = copy.deepcopy(base) if dry_run else base
    preview: list[str] = []
    for item in additions:
        _rt, _rv, created = apply_rule_to_project(
            work,
            project_name=item["project_name"],
            rule_type=item["rule_type"],
            rule_value=item["rule_value"],
        )
        verb = "add (new project)" if created else "add"
        preview.append(
            f"{verb}: {item['project_name']} match_terms={item['rule_value']!r}"
        )

    console.print("\n".join(preview))
    if dry_run:
        console.print("[yellow]Dry run — config not written.[/yellow]")
        raise typer.Exit(code=0)

    backup = backup_projects_config_if_exists(cfg_path)
    if backup:
        console.print(f"[dim]Backup:[/dim] {backup}")
    save_projects_config_payload(cfg_path, work)
    console.print("[green]projects-anchor: config updated.[/green]")
