"""Typer command: guided day-level gap triage."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import timedelta
from typing import Annotated, Any, Optional
from urllib.parse import urlparse

import questionary
import typer

from collectors.chrome import chrome_ts
from core.chrome_epoch import CHROME_EPOCH_DELTA_US
from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.config import as_list, default_projects_config_option, load_projects_config_payload, normalize_profile
from core.calibration.screen_time_gap import analyze_screen_time_gaps
from core.cli_prompts import prompt_for_timeframe
from core.guided_project_config import build_guided_config_plan
from core.triage_code_repos import build_code_repo_candidates
from scripts.calibration.gap_day_triage import (
    DayTopSite,
    ProjectSuggestion,
    apply_domain_mappings,
    fetch_chrome_rows_for_day,
    score_projects_for_sites,
    summarize_day_sites,
)

AGENT_TRIAGE_SCHEMA_VERSION = 1

NOTES_FOR_AGENTS = [
    "JSON mode omits Chrome page titles to reduce accidental PII in logs; domains and counts remain.",
    "Primary mapping signal is tracked_urls / site-first scoring; match_terms is secondary.",
    "Use --json for read-only plans only. Apply explicit decisions with `gittan triage-apply`; never pipe raw --json output into config.",
    "To apply decisions from mobile/offline UIs, use `gittan triage-apply` with a decisions JSON (see docs/runbooks/gittan-triage-agents.md) — not the triage --json plan.",
    "Top-site timestamp hints are local-time anchors only (first/last/sample window), not page-title evidence.",
    "Triage uses a noise pre-pass that removes known Cursor SDK/skills/tooling chatter before project suggestions.",
]

TRIAGE_NOISE_DOMAINS = {
    "cursor.com",
    "www.cursor.com",
    "cursor.sh",
    "www.cursor.sh",
}

TRIAGE_NOISE_TITLE_MARKERS = (
    "canvas sdk mirror failed",
    "skills-cursor",
    "cursor sdk",
    "mcp tool schema",
    "cursor extension host",
    "cursor diagnostics",
)


def load_triage_profiles(projects_config: str) -> list[dict]:
    payload = load_projects_config_payload(Path(projects_config))
    profiles: list[dict] = []
    for raw in payload.get("projects", []):
        if not isinstance(raw, dict) or not bool(raw.get("enabled", True)):
            continue
        profiles.append(normalize_profile(raw))
    return profiles


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower().strip()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _build_site_time_hints(chrome_rows: list[tuple[int, str, str]]) -> dict[str, dict[str, Any]]:
    # Domain-level timing anchors for faster mapping decisions in onboarding UIs.
    by_domain: dict[str, list[int]] = {}
    for visit_time_cu, url, _title in chrome_rows:
        domain = _extract_domain(url)
        if not domain:
            continue
        by_domain.setdefault(domain, []).append(int(visit_time_cu))
    out: dict[str, dict[str, Any]] = {}
    for domain, times in by_domain.items():
        if not times:
            continue
        times.sort()
        first_dt = chrome_ts(times[0], CHROME_EPOCH_DELTA_US).astimezone()
        last_dt = chrome_ts(times[-1], CHROME_EPOCH_DELTA_US).astimezone()
        sample_end = min(last_dt, first_dt + timedelta(minutes=15))
        out[domain] = {
            "first_seen_local": first_dt.isoformat(timespec="seconds"),
            "last_seen_local": last_dt.isoformat(timespec="seconds"),
            "sample_window_local": {
                "start": first_dt.isoformat(timespec="seconds"),
                "end": sample_end.isoformat(timespec="seconds"),
            },
        }
    return out


def _is_triage_noise_row(url: str, title: str) -> bool:
    domain = _extract_domain(url)
    if domain in TRIAGE_NOISE_DOMAINS:
        return True
    text = (title or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in TRIAGE_NOISE_TITLE_MARKERS)


def _filter_triage_noise_rows(
    chrome_rows: list[tuple[int, str, str]],
) -> tuple[list[tuple[int, str, str]], int]:
    filtered: list[tuple[int, str, str]] = []
    dropped = 0
    for row in chrome_rows:
        _visit_time_cu, url, title = row
        if _is_triage_noise_row(url, title):
            dropped += 1
            continue
        filtered.append(row)
    return filtered, dropped
def _site_to_plan_dict(site: DayTopSite, site_time_hints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "domain": site.domain,
        "visits": site.visits,
        "share": round(float(site.share), 6),
    }
    timing = site_time_hints.get(site.domain)
    if timing:
        payload.update(timing)
    return payload
def _suggestion_to_plan_dict(s: ProjectSuggestion, tags: list[str]) -> dict[str, Any]:
    return {
        "canonical": s.canonical,
        "score": s.score,
        "aliases": list(s.aliases),
        "explicit_domain_hits": s.explicit_domain_hits,
        "term_hits": s.term_hits,
        "alias_or_name_hits": s.alias_or_name_hits,
        "ticket_mode": s.ticket_mode,
        "default_client": s.default_client,
        "tags": tags,
    }
def _build_choices(
    suggestions: list[ProjectSuggestion],
    tags_by_canonical: dict[str, list[str]],
    max_choices: int = 3,
) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    for s in suggestions[: max(0, max_choices - 1)]:
        tags = tags_by_canonical.get(s.canonical, [])
        tag_prefix = f"#PROJ-{tags[0].upper()} · " if tags else "#PROJ · "
        choices.append({"canonical": s.canonical, "tags": tags, "label": f"{tag_prefix}{s.canonical}"})
    choices.append({"canonical": None, "tags": [], "label": "None of these / skip"})
    return choices
def _build_question(gap: dict[str, Any], suggestions: list[ProjectSuggestion]) -> Optional[str]:
    hours = float(gap.get("unexplained_screen_time_hours", 0.0))
    day = gap.get("day", "?")
    if not suggestions:
        return None
    if len(suggestions) == 1:
        return f"Does this {hours:.1f}h on {day} belong to {suggestions[0].canonical}?"
    return f"Does this {hours:.1f}h on {day} belong to {suggestions[0].canonical} or {suggestions[1].canonical}?"


def _yes_automation_plan(
    *,
    suggestions: list[ProjectSuggestion],
    profiles: list[dict],
    all_names: list[str],
    top_sites: list[DayTopSite],
    projects_payload: dict[str, Any],
    day: str,
) -> dict[str, Any]:
    suggested_project = resolve_target_project_name(profiles, suggestions[0].canonical) if suggestions else None
    return {
        "would_apply": False,
        "reason": "explicit_decision_required",
        "target_project": suggested_project,
    }


def build_triage_plan_dict(
    *,
    date_from: Optional[str],
    date_to: Optional[str],
    projects_config: str,
    max_days: int,
    max_sites: int,
    scoring_mode: str,
    home: Optional[Path] = None,
) -> dict[str, Any]:
    """Assemble the read-only triage plan (same inputs as the CLI). Intended for --json and tests."""
    from core.report_service import run_timelog_report

    root_home = home if home is not None else Path.home()
    options = TimelogRunOptions(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
    payload = analyze_screen_time_gaps(report)
    day_rows = select_triage_days(payload, max_days=max_days)
    profiles = load_triage_profiles(projects_config)
    projects_payload = load_projects_config_payload(Path(projects_config))
    all_names = sorted(
        {
            str(profile.get("name", "")).strip()
            for profile in profiles
            if str(profile.get("name", "")).strip()
        }
    )
    tags_by_canonical: dict[str, list[str]] = {}
    for p in profiles:
        c = str(p.get("canonical_project", p.get("name", ""))).strip()
        for tag in p.get("tags", []):
            if tag not in tags_by_canonical.get(c, []):
                tags_by_canonical.setdefault(c, []).append(tag)
    out_days: list[dict[str, Any]] = []
    empty_reason: Optional[str] = None
    if not day_rows:
        empty_reason = "no_unexplained_days"

    for row in day_rows:
        day = str(row.get("day"))
        chrome_rows = fetch_chrome_rows_for_day(day, home=root_home)
        signal_rows, noise_rows_filtered = _filter_triage_noise_rows(chrome_rows)
        top_sites = summarize_day_sites(signal_rows, limit=max_sites)
        code_repos = build_code_repo_candidates(signal_rows, limit=max_sites)
        site_time_hints = _build_site_time_hints(signal_rows)
        suggestions = score_projects_for_sites(profiles, top_sites, scoring_mode=scoring_mode)
        skip_reason: Optional[str] = None
        if not top_sites:
            skip_reason = "no_chrome_sites"
        elif not suggestions:
            skip_reason = "no_suggestions"

        resolved: Optional[str] = None
        resolved_ok: Optional[bool] = None
        yes_automation: dict[str, Any]
        if suggestions:
            resolved = resolve_target_project_name(profiles, suggestions[0].canonical)
            resolved_ok = resolved in all_names
            yes_automation = _yes_automation_plan(
                suggestions=suggestions,
                profiles=profiles,
                all_names=all_names,
                top_sites=top_sites,
                projects_payload=projects_payload,
                day=day,
            )
        else:
            yes_automation = {"would_apply": False, "reason": "no_suggestions"}

        gap_data = {
            "estimated_hours": float(row.get("estimated_hours", 0.0)),
            "screen_time_hours": float(row.get("screen_time_hours", 0.0)),
            "unexplained_screen_time_hours": float(row.get("unexplained_screen_time_hours", 0.0)),
        }
        out_days.append(
            {
                "day": day,
                "gap": gap_data,
                "top_sites": [_site_to_plan_dict(s, site_time_hints) for s in top_sites],
                "code_repos": code_repos,
                "noise_rows_filtered": int(noise_rows_filtered),
                "suggestions": [
                    _suggestion_to_plan_dict(s, tags_by_canonical.get(s.canonical, []))
                    for s in suggestions
                ],
                "question": _build_question({**gap_data, "day": day}, suggestions),
                "choices": _build_choices(suggestions, tags_by_canonical),
                "resolved_project_for_top_suggestion": resolved,
                "resolved_in_config": resolved_ok,
                "yes_automation": yes_automation,
                "skip_reason": skip_reason,
            }
        )

    return {
        "schema_version": AGENT_TRIAGE_SCHEMA_VERSION,
        "command": "gittan triage",
        "options": {
            "date_from": date_from,
            "date_to": date_to,
            "projects_config": projects_config,
            "max_days": int(max_days),
            "max_sites": int(max_sites),
            "scoring_mode": scoring_mode,
        },
        "project_names": all_names,
        "empty_reason": empty_reason,
        "days": out_days,
        "guided_config": build_guided_config_plan(
            projects_payload=projects_payload,
            triage_days=out_days,
            projects_config=projects_config,
        ),
        "notes_for_agents": list(NOTES_FOR_AGENTS),
    }


def select_triage_days(payload: dict, *, max_days: int) -> list[dict]:
    if int(max_days) < 1:
        raise ValueError(f"max_days must be at least 1, got {max_days}")
    rows = [
        row
        for row in payload.get("days", [])
        if float(row.get("unexplained_screen_time_hours", 0.0)) > 0
    ]
    rows.sort(
        key=lambda row: float(row.get("unexplained_screen_time_hours", 0.0)),
        reverse=True,
    )
    return rows[: int(max_days)]


def resolve_target_project_name(profiles: list[dict], canonical: str) -> str:
    clean = canonical.strip().lower()
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if name.lower() == clean:
            return name
    for profile in profiles:
        if str(profile.get("canonical_project", "")).strip().lower() == clean:
            return str(profile.get("name", "")).strip()
    return canonical


def _render_day_summary(row: dict, top_sites: list[DayTopSite]) -> str:
    lines = [
        f"Day: {row.get('day')}",
        f"  Estimated: {float(row.get('estimated_hours', 0.0)):.2f}h",
        f"  Screen: {float(row.get('screen_time_hours', 0.0)):.2f}h",
        f"  Unexplained: {float(row.get('unexplained_screen_time_hours', 0.0)):.2f}h",
        "  Top sites:",
    ]
    for site in top_sites:
        lines.append(f"    - {site.domain} ({site.visits} visits)")
    return "\n".join(lines)


def _render_triage_next_steps(projects_config: str) -> str:
    return (
        "[bold]Next steps:[/bold]\n"
        "  1. Run [cyan]gittan triage --json[/cyan] to collect read-only evidence candidates.\n"
        "  2. Build a [cyan]decisions[/cyan] JSON with confirmed mappings only.\n"
        f"  3. Preview writes with [cyan]gittan triage-apply --dry-run --projects-config {projects_config} --input decisions.json[/cyan].\n"
        f"  4. Apply after review with [cyan]gittan triage-apply --interactive-review --projects-config {projects_config} --input decisions.json[/cyan]."
    )


def _resolve_date_range_with_picker(*, date_from: Optional[str], date_to: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Use the shared timeframe picker when triage runs without date flags."""
    if date_from or date_to:
        return date_from, date_to
    if not sys.stdin.isatty():
        return date_from, date_to
    print("No date flags provided - choose timeframe interactively.")
    picked = prompt_for_timeframe()
    return picked.get("date_from"), picked.get("date_to")


@app.command("triage")
def triage(
    date_from: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    max_days: Annotated[int, typer.Option(help="Max unexplained days to review")] = 3,
    max_sites: Annotated[int, typer.Option(help="Top sites shown/mappable per day")] = 5,
    scoring_mode: Annotated[str, typer.Option(help="balanced or site-first")] = "site-first",
    yes: Annotated[bool, typer.Option(help="Deprecated: heuristic auto-apply is disabled")] = False,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Print read-only JSON plan to stdout; never writes config"),
    ] = False,
):
    """Guided loop: confirm/correct project mapping on top unexplained days."""
    from rich.console import Console

    from core.report_service import run_timelog_report

    console = Console()
    if json_out and yes:
        console.print("[red]Cannot combine --json with --yes.[/red] Use --json alone for a read-only plan.")
        raise typer.Exit(code=1)
    if scoring_mode not in {"balanced", "site-first"}:
        console.print(f"[red]Invalid --scoring-mode:[/red] {scoring_mode!r} (use balanced or site-first)")
        raise typer.Exit(code=1)
    if int(max_days) < 1:
        console.print(f"[red]Invalid --max-days:[/red] must be at least 1, got {max_days}")
        raise typer.Exit(code=1)
    if yes:
        console.print(
            "[yellow]`gittan triage --yes` no longer applies heuristic mappings.[/yellow] "
            "Use `gittan triage --json` to review evidence, then `gittan triage-apply` with explicit decisions."
        )
        console.print(_render_triage_next_steps(projects_config))
        raise typer.Exit(code=1)
    date_from, date_to = _resolve_date_range_with_picker(date_from=date_from, date_to=date_to)
    if json_out:
        stderr_console = Console(stderr=True)
        stderr_console.print("[dim]Producing read-only triage JSON evidence (no config changes)...[/dim]")
        with stderr_console.status("[bold blue]Producing triage evidence JSON...[/bold blue]", spinner="dots"):
            plan = build_triage_plan_dict(
                date_from=date_from,
                date_to=date_to,
                projects_config=projects_config,
                max_days=max_days,
                max_sites=max_sites,
                scoring_mode=scoring_mode,
            )
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0)

    options = TimelogRunOptions(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
    payload = analyze_screen_time_gaps(report)
    days = select_triage_days(payload, max_days=max_days)
    if not days:
        console.print("[green]No unexplained days to triage in this range.[/green]")
        raise typer.Exit(code=0)

    profiles = load_triage_profiles(projects_config)
    all_names = sorted(
        {
            str(profile.get("name", "")).strip()
            for profile in profiles
            if str(profile.get("name", "")).strip()
        }
    )
    projects_payload = load_projects_config_payload(Path(projects_config))
    applied_total = 0
    for row in days:
        day = str(row.get("day"))
        chrome_rows = fetch_chrome_rows_for_day(day, home=Path.home())
        signal_rows, noise_rows_filtered = _filter_triage_noise_rows(chrome_rows)
        top_sites = summarize_day_sites(signal_rows, limit=max_sites)
        suggestions = score_projects_for_sites(profiles, top_sites, scoring_mode=scoring_mode)
        console.print("")
        if noise_rows_filtered:
            console.print(
                f"[dim]Noise pre-pass filtered {noise_rows_filtered} row(s) before scoring.[/dim]"
            )
        console.print(_render_day_summary(row, top_sites))
        if not top_sites:
            continue
        if not suggestions:
            console.print("[yellow]No project suggestions found; skipping day.[/yellow]")
            continue
        suggested_project = resolve_target_project_name(profiles, suggestions[0].canonical)
        project_choice = questionary.select(
            f"{day}: choose project",
            choices=[*all_names, "Skip day"],
            default=suggested_project if suggested_project in all_names else None,
        ).ask()
        if not project_choice or project_choice == "Skip day":
            continue
        target = project_choice
        selected_domains = questionary.checkbox(
            f"{day}: pick domains to map to '{target}'",
            choices=[site.domain for site in top_sites],
            validate=lambda value: True if value else "Select at least one domain or skip day.",
        ).ask()
        if not selected_domains:
            continue
        assignments = [(domain, target) for domain in as_list(selected_domains)]
        if not assignments:
            continue
        applied, _created = apply_domain_mappings(
            Path(projects_config),
            assignments,
            allow_create_projects=False,
        )
        applied_total += applied
        console.print(f"[green]Applied[/green] {applied} mapping(s) for {day} -> {target}")
        profiles = load_triage_profiles(projects_config)
        projects_payload = load_projects_config_payload(Path(projects_config))
    console.print(f"\n[bold]Triage complete.[/bold] applied mappings: {applied_total}")
    console.print(_render_triage_next_steps(projects_config))

