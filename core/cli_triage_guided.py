"""Typer command: lightweight guided triage with explicit apply confirmation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Optional

import questionary
import typer

from core.cli_app import app
from core.cli_date_range import resolve_date_window
from core.cli_options import TimelogRunOptions
from core.cli_triage import (
    _filter_triage_noise_rows,
    build_triage_plan_dict,
    load_triage_profiles,
    resolve_target_project_name,
)
from core.cli_triage_apply import apply_triage_decisions_payload
from core.config import default_projects_config_option
from core.report_nudges import (
    UNCATEGORIZED_NUDGE_THRESHOLD_HOURS,
    UNCATEGORIZED_NUDGE_THRESHOLD_RATIO,
    uncategorized_hours_by_day,
)

DEFAULT_GUIDED_RECENT_DAYS = 7
_DECISIONS_SCHEMA_VERSION = 1


def _build_guided_decisions(
    plan_days: list[dict[str, Any]],
    project_names: set[str],
) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    for day in plan_days:
        suggested = str(day.get("resolved_project_for_top_suggestion") or "").strip()
        if not suggested or suggested not in project_names:
            continue
        top_sites = day.get("top_sites", [])
        domains = [str(item.get("domain", "")).strip() for item in top_sites if str(item.get("domain", "")).strip()]
        if not domains:
            continue
        include_day = questionary.confirm(
            f"{day.get('day')}: map top domains to '{suggested}'?",
            default=True,
        ).ask()
        if not include_day:
            continue
        picked_domains = questionary.checkbox(
            f"{day.get('day')}: choose domains",
            choices=domains,
        ).ask() or []
        for domain in picked_domains:
            decisions.append(
                {
                    "project_name": suggested,
                    "rule_type": "tracked_urls",
                    "rule_value": str(domain),
                }
            )
    return decisions


def _build_decisions_payload(decisions: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": _DECISIONS_SCHEMA_VERSION,
        "decisions": decisions,
    }


def _write_decisions_file(path: str, decisions: list[dict[str, str]]) -> Path:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _build_decisions_payload(decisions)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path


def _top_uncategorized_days(report, *, max_days: int) -> list[str]:
    uncategorized = uncategorized_hours_by_day(report)
    if not uncategorized:
        return []
    ranked = sorted(uncategorized.items(), key=lambda item: item[1], reverse=True)
    out: list[str] = []
    candidates: list[str] = []
    for day, unc_h in ranked[: max(1, int(max_days))]:
        total_h = float((report.overall_days.get(day, {}) or {}).get("hours", 0.0) or 0.0)
        ratio = (unc_h / total_h) if total_h > 0 else 0.0
        if unc_h < float(UNCATEGORIZED_NUDGE_THRESHOLD_HOURS) and ratio < float(UNCATEGORIZED_NUDGE_THRESHOLD_RATIO):
            continue
        out.append(day)
        candidates.append(f"{day} ({unc_h:.1f}h, {ratio:.0%})")
    return out


def _render_uncategorized_fallback(*, report, date_from: Optional[str], date_to: Optional[str], max_days: int) -> str | None:
    candidates = _top_uncategorized_days(report, max_days=max_days)
    if not candidates:
        return None
    from_s = date_from or "auto"
    to_s = date_to or "auto"
    return (
        "No unexplained gap days were found, but Uncategorized time is significant.\n"
        f"Candidates: {', '.join(candidates)}\n"
        "Guided mode will derive candidate mappings from top Chrome domains and still require explicit confirmation.\n"
        f"Range: --from {from_s} --to {to_s}."
    )


def _build_uncategorized_plan_days(*, report, projects_config: str, max_days: int, max_sites: int, scoring_mode: str) -> list[dict[str, Any]]:
    from scripts.calibration.gap_day_triage import fetch_chrome_rows_for_day, score_projects_for_sites, summarize_day_sites

    profiles = load_triage_profiles(projects_config)
    days = _top_uncategorized_days(report, max_days=max_days)
    if not days:
        return []
    plan_days: list[dict[str, Any]] = []
    for day in days:
        chrome_rows = fetch_chrome_rows_for_day(day, home=Path.home())
        signal_rows, noise_rows_filtered = _filter_triage_noise_rows(chrome_rows)
        top_sites = summarize_day_sites(signal_rows, limit=max_sites)
        if not top_sites:
            if noise_rows_filtered:
                continue
            continue
        suggestions = score_projects_for_sites(profiles, top_sites, scoring_mode=scoring_mode)
        if not suggestions:
            continue
        resolved = resolve_target_project_name(profiles, suggestions[0].canonical)
        plan_days.append(
            {
                "day": day,
                "skip_reason": None,
                "resolved_project_for_top_suggestion": resolved,
                "top_sites": [{"domain": site.domain} for site in top_sites],
            }
        )
    return plan_days


@app.command("triage-guided")
def triage_guided(
    date_from: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    max_days: Annotated[int, typer.Option(help="Max unexplained days to review")] = 3,
    max_sites: Annotated[int, typer.Option(help="Top sites shown/mappable per day")] = 5,
    scoring_mode: Annotated[str, typer.Option(help="balanced or site-first")] = "site-first",
    write_decisions: Annotated[
        Optional[str],
        typer.Option("--write-decisions", help="Write generated decisions JSON to path"),
    ] = None,
) -> None:
    """Guide triage flow: evidence -> dry-run preview -> explicit apply confirm."""
    from rich.console import Console
    from core.report_service import run_timelog_report

    console = Console()
    date_from, date_to = resolve_date_window(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        fallback_recent_days=DEFAULT_GUIDED_RECENT_DAYS,
    )
    plan = build_triage_plan_dict(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        max_days=max_days,
        max_sites=max_sites,
        scoring_mode=scoring_mode,
    )
    days = [d for d in plan.get("days", []) if not d.get("skip_reason")]
    if not days:
        options = TimelogRunOptions(
            date_from=date_from,
            date_to=date_to,
            projects_config=projects_config,
            include_uncategorized=True,
            quiet=True,
            screen_time="on",
        )
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
        fallback = _render_uncategorized_fallback(
            report=report,
            date_from=date_from,
            date_to=date_to,
            max_days=max_days,
        )
        if fallback:
            console.print(f"[yellow]{fallback}[/yellow]")
            fallback_days = _build_uncategorized_plan_days(
                report=report,
                projects_config=projects_config,
                max_days=max_days,
                max_sites=max_sites,
                scoring_mode=scoring_mode,
            )
            project_names = set(str(name) for name in plan.get("project_names", []))
            fallback_decisions = _build_guided_decisions(fallback_days, project_names)
            if write_decisions:
                written_path = _write_decisions_file(write_decisions, fallback_decisions)
                console.print(
                    "[green]Decisions file written:[/green] "
                    f"{written_path} ({len(fallback_decisions)} decision(s) from uncategorized fallback)"
                )
            if fallback_decisions:
                preview = apply_triage_decisions_payload(
                    decisions=fallback_decisions,
                    projects_config=projects_config,
                    allow_create=False,
                    dry_run=True,
                    interactive_review=False,
                )
                if preview.get("errors"):
                    console.print(json.dumps(preview, indent=2))
                    raise typer.Exit(code=1)
                console.print(preview.get("preview", "No preview available."))
                confirmed = questionary.confirm("Apply these fallback changes to config now?", default=False).ask()
                if not confirmed:
                    console.print("[yellow]Cancelled before writing config.[/yellow]")
                    raise typer.Exit(code=0)
                applied = apply_triage_decisions_payload(
                    decisions=fallback_decisions,
                    projects_config=projects_config,
                    allow_create=False,
                    dry_run=False,
                    interactive_review=False,
                )
                if applied.get("errors"):
                    console.print(json.dumps(applied, indent=2))
                    raise typer.Exit(code=1)
                console.print(json.dumps(applied, indent=2))
                console.print("[green]Guided triage apply complete (uncategorized fallback).[/green]")
            raise typer.Exit(code=0)
        console.print("[green]No unexplained days with suggestions in this range.[/green]")
        raise typer.Exit(code=0)

    project_names = set(str(name) for name in plan.get("project_names", []))
    decisions = _build_guided_decisions(days, project_names)
    if not decisions:
        if write_decisions:
            console.print("[yellow]No decisions selected. Decisions file not written.[/yellow]")
        console.print("[yellow]No decisions selected. Nothing to apply.[/yellow]")
        raise typer.Exit(code=0)
    if write_decisions:
        written_path = _write_decisions_file(write_decisions, decisions)
        console.print(f"[green]Decisions file written:[/green] {written_path}")

    preview = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=projects_config,
        allow_create=False,
        dry_run=True,
        interactive_review=False,
    )
    if preview.get("errors"):
        console.print(json.dumps(preview, indent=2))
        raise typer.Exit(code=1)
    console.print(preview.get("preview", "No preview available."))

    confirmed = questionary.confirm("Apply these changes to config now?", default=False).ask()
    if not confirmed:
        console.print("[yellow]Cancelled before writing config.[/yellow]")
        raise typer.Exit(code=0)

    applied = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=projects_config,
        allow_create=False,
        dry_run=False,
        interactive_review=False,
    )
    if applied.get("errors"):
        console.print(json.dumps(applied, indent=2))
        raise typer.Exit(code=1)
    console.print(json.dumps(applied, indent=2))
    console.print("[green]Guided triage apply complete.[/green]")
