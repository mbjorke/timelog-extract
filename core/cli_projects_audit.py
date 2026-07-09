"""Typer commands: projects-audit (usage stats), projects-trim (remove rules)."""

from __future__ import annotations

import copy
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
    is_ephemeral_anchor_kind,
    normalize_anchor_kind,
)
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
    SIGNAL_KIND_LABELS,
    TRIM_PLAN_SCHEMA_VERSION,
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
        typer.Option(help="Max rows per kind in top_signals (hosts/dirs/branches/titles; 0 disables)"),
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
                f"unanchored signals (host → tracked_urls; repo/dir → match_terms) at "
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
        out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not json_out:
            console.print(
                f"[dim]Wrote trim plan ({plan['meta']['zero_hit_candidates']} zero-hit candidates) "
                f"to {out_path} (schema v{TRIM_PLAN_SCHEMA_VERSION}). "
                f"Review; then `gittan projects-trim -i {out_path}` --dry-run.[/dim]"
            )

    if write_anchor_plan:
        floor = 1 if unsafe_low_floor else max(1, int(min_hits))
        if floor < ANCHOR_PLAN_APPLY_MIN_HITS and not json_out:
            console.print(
                f"[yellow]Warning:[/yellow] min_hits={floor} is below the safe floor "
                f"({ANCHOR_PLAN_APPLY_MIN_HITS}); one-off noise can become permanent "
                "match_terms."
            )
        plan = build_anchor_plan_from_audit(
            payload,
            min_hits=floor,
            include_ephemeral_kinds=include_ephemeral_kinds,
        )
        out_path = Path(write_anchor_plan).expanduser()
        out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not json_out:
            inv_n = int(plan["meta"].get("inventory_candidates", 0) or 0)
            inv_note = f", {inv_n} inventory (branch/label)" if inv_n else ""
            console.print(
                f"[dim]Wrote anchor plan ({plan['meta']['anchor_candidates']} apply candidates"
                f"{inv_note}) to {out_path} (schema v{ANCHOR_PLAN_SCHEMA_VERSION}, "
                f"min_hits={plan['meta']['min_hits']}). "
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
    if int(max_top_hosts) > 0 and payload.get("top_signals"):
        console.print()
        console.print(f"[dim]{payload.get('top_signals_note', '')}[/dim]")
        st = Table(show_header=True, header_style="bold")
        st.add_column("Kind")
        st.add_column("Signal")
        st.add_column("Rule", justify="center")
        st.add_column("Hits", justify="right")
        st.add_column("Anchored", justify="center")
        for row in payload["top_signals"]:
            st.add_row(
                SIGNAL_KIND_LABELS.get(str(row.get("kind", "")), str(row.get("kind", ""))),
                str(row.get("value", "")),
                str(row.get("rule_type", "")),
                str(row.get("hits", 0)),
                "yes" if row.get("anchored") else "no",
            )
        console.print(st)
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
        try:
            kind = normalize_anchor_kind(str(item.get("anchor_kind", "")))
        except ValueError as exc:
            raise ValueError(f"additions[{idx}]: {exc}") from exc
        hits_raw = item.get("hits")
        hits: int | None
        if hits_raw is None or hits_raw == "":
            hits = None
        else:
            try:
                hits = int(hits_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"additions[{idx}]: hits must be an integer") from exc
        if not pn or not rv:
            raise ValueError(f"additions[{idx}]: project_name and rule_value required")
        if rt not in {"match_terms", "tracked_urls"}:
            raise ValueError(f"additions[{idx}]: rule_type must be match_terms or tracked_urls")
        out.append(
            {
                "project_name": pn,
                "rule_type": rt,
                "rule_value": rv,
                "anchor_kind": kind,
                "hits": hits,
            }
        )
    return out


@app.command("projects-anchor")
def projects_anchor(
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    input_path: Annotated[
        Optional[str],
        typer.Option("-i", "--input", help="JSON file with additions (use - for stdin)"),
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Print planned additions only; no write")] = False,
    include_ephemeral_kinds: Annotated[
        bool,
        typer.Option(
            "--include-ephemeral-kinds",
            help=(
                "Apply branch/label rows (default: skip them). Prefer attaching repo/dir "
                "to an existing customer/line instead of permanent match_terms from "
                "ephemeral session context."
            ),
        ),
    ] = False,
    min_hits: Annotated[
        int,
        typer.Option(
            "--min-hits",
            help=(
                f"Skip rows whose hits are below this floor when hits are present "
                f"(default {ANCHOR_PLAN_APPLY_MIN_HITS}). Rows without hits still apply."
            ),
        ),
    ] = ANCHOR_PLAN_APPLY_MIN_HITS,
) -> None:
    """Add rules from an anchor plan (stable signals: hosts, repos, dirs by default)."""
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

    floor = max(1, int(min_hits))
    skipped: list[str] = []
    apply_rows: list[dict[str, Any]] = []
    for item in additions:
        kind = item.get("anchor_kind") or ""
        if is_ephemeral_anchor_kind(kind) and not include_ephemeral_kinds:
            skipped.append(
                f"skip ephemeral {kind}: {item['project_name']} "
                f"{item['rule_type']}={item['rule_value']!r}"
            )
            continue
        hits = item.get("hits")
        if hits is not None and int(hits) < floor:
            skipped.append(
                f"skip low-hit ({hits}<{floor}): {item['project_name']} "
                f"{item['rule_type']}={item['rule_value']!r}"
            )
            continue
        apply_rows.append(item)

    if skipped:
        console.print(f"[dim]skipped {len(skipped)} ephemeral/low-hit candidate(s)[/dim]")
    for line in skipped:
        console.print(f"[dim]{line}[/dim]")

    if not apply_rows:
        console.print(
            "[yellow]No apply candidates left "
            "(plan was only ephemeral/low-hit rows, or empty after filter). "
            "Re-run with --include-ephemeral-kinds and/or a lower --min-hits only if "
            "you intentionally want those rows as permanent rules.[/yellow]"
        )
        raise typer.Exit(code=1)

    cfg_path = Path(projects_config).expanduser()
    base = load_projects_config_payload(cfg_path)
    work = copy.deepcopy(base) if dry_run else base
    preview: list[str] = []
    for item in apply_rows:
        _rt, _rv, created = apply_rule_to_project(
            work,
            project_name=item["project_name"],
            rule_type=item["rule_type"],
            rule_value=item["rule_value"],
        )
        verb = "add (new project)" if created else "add"
        preview.append(
            f"{verb}: {item['project_name']} {item['rule_type']}={item['rule_value']!r}"
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
