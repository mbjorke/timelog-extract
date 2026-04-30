"""Typer command: lightweight guided triage with explicit apply confirmation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Optional
from urllib.parse import urlparse

import questionary
import typer
from questionary import Choice

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


def _domain_checkbox_choices_with_context(
    top_sites: list[dict[str, Any]],
    *,
    suggested_project: str,
    domain_project_counts: dict[str, list[dict[str, Any]]] | None,
) -> list[Choice]:
    choices: list[Choice] = []
    history_map = domain_project_counts or {}
    project_key = str(suggested_project or "").strip().lower()
    generic_domains = {
        "google.com",
        "github.com",
        "claude.ai",
        "accounts.google.com",
        "mail.google.com",
        "linkedin.com",
        "messenger.com",
        "tunnistautuminen.suomi.fi",
    }
    for item in top_sites:
        domain = str(item.get("domain", "")).strip()
        if not domain:
            continue
        repo_hint = str(item.get("repo_hint", "")).strip()
        sample_title = str(item.get("sample_title", "")).strip()
        title_preview = sample_title.replace("\n", " ").strip()
        if len(title_preview) > 60:
            title_preview = title_preview[:57].rstrip() + "..."
        history = history_map.get(domain, [])
        history_preview = ", ".join(
            f"{str(entry.get('project', '')).strip()} ({int(entry.get('events', 0) or 0)})"
            for entry in history
            if str(entry.get("project", "")).strip()
        )
        parts = [domain]
        if repo_hint:
            parts.append(repo_hint)
        if title_preview:
            parts.append(title_preview)
        if history_preview:
            parts.append(f"often: {history_preview}")
        label = " — ".join(parts)
        is_generic = domain.lower() in generic_domains
        direct_signal = bool(project_key and (project_key in domain.lower() or project_key in repo_hint.lower()))
        hist = history_map.get(domain, [])
        hist_total = sum(int(entry.get("events", 0) or 0) for entry in hist)
        hist_target = sum(
            int(entry.get("events", 0) or 0)
            for entry in hist
            if str(entry.get("project", "")).strip().lower() == project_key
        )
        hist_dominant = bool(hist_total > 0 and hist_target >= 3 and (hist_target / hist_total) >= 0.7)
        low_confidence = is_generic and not (direct_signal or hist_dominant)
        if low_confidence:
            label = f"{label} — [low confidence: generic domain]"
            choices.append(Choice(title=label, value=domain, disabled="Needs stronger signal"))
        else:
            choices.append(Choice(title=label, value=domain))
    return choices


def _build_guided_decisions(
    plan_days: list[dict[str, Any]],
    project_names: set[str],
    *,
    domain_project_counts: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    for day in plan_days:
        suggested = str(day.get("resolved_project_for_top_suggestion") or "").strip()
        if not suggested or suggested not in project_names:
            continue
        top_sites = day.get("top_sites", [])
        domain_choices = _domain_checkbox_choices_with_context(
            top_sites,
            suggested_project=suggested,
            domain_project_counts=domain_project_counts,
        )
        if not domain_choices:
            continue
        include_day = questionary.confirm(
            f"{day.get('day')}: map top domains to project '{suggested}'?",
            default=True,
        ).ask()
        if include_day is None:
            raise KeyboardInterrupt("triage guided cancelled by user")
        if not include_day:
            continue
        picked_domains = questionary.checkbox(
            f"{day.get('day')}: choose domains for project '{suggested}'",
            choices=domain_choices,
        ).ask()
        if picked_domains is None:
            raise KeyboardInterrupt("triage guided cancelled by user")
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
    cap = max(1, int(max_days))
    for day, unc_h in ranked:
        total_h = float((report.overall_days.get(day, {}) or {}).get("hours", 0.0) or 0.0)
        ratio = (unc_h / total_h) if total_h > 0 else 0.0
        if unc_h < float(UNCATEGORIZED_NUDGE_THRESHOLD_HOURS) or ratio < float(UNCATEGORIZED_NUDGE_THRESHOLD_RATIO):
            continue
        out.append(day)
        candidates.append(f"{day} ({unc_h:.1f}h, {ratio:.0%})")
        if len(out) >= cap:
            break
    return out


def _render_uncategorized_fallback(*, report, date_from: Optional[str], date_to: Optional[str], max_days: int) -> str | None:
    candidates = _top_uncategorized_days(report, max_days=max_days)
    if not candidates:
        return None
    range_args: list[str] = []
    if date_from:
        range_args.append(f"--from {date_from}")
    if date_to:
        range_args.append(f"--to {date_to}")
    range_hint = f" Range: {' '.join(range_args)}." if range_args else ""
    return (
        "No eligible suggested days were available, but Uncategorized time is significant.\n"
        f"Candidates: {', '.join(candidates)}\n"
        "Guided mode will derive candidate mappings from top Chrome domains and still require explicit confirmation.\n"
        f"{range_hint}"
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
        domain_repo_hints = _repo_hints_by_domain(signal_rows)
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
                "top_sites": [
                    {
                        "domain": site.domain,
                        "sample_title": str(site.sample_title or ""),
                        "repo_hint": domain_repo_hints.get(site.domain, ""),
                    }
                    for site in top_sites
                ],
            }
        )
    return plan_days


def _repo_hints_by_domain(rows: list[tuple[int, str, str]]) -> dict[str, str]:
    counts: dict[str, dict[str, int]] = {}
    for _visit_time_cu, url, _title in rows:
        domain, repo = _extract_domain_repo_hint(url)
        if not domain or not repo:
            continue
        counts.setdefault(domain, {})
        counts[domain][repo] = counts[domain].get(repo, 0) + 1
    out: dict[str, str] = {}
    for domain, per_repo in counts.items():
        out[domain] = sorted(per_repo.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return out


def _extract_domain_repo_hint(url: str) -> tuple[str, str]:
    text = str(url or "").strip()
    if not text:
        return "", ""
    try:
        parsed = urlparse(text)
    except Exception:
        return "", ""
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    if host != "github.com":
        return host, ""
    segments = [part.strip() for part in parsed.path.split("/") if part.strip()]
    if len(segments) < 2:
        return host, ""
    owner, repo = segments[0], segments[1]
    if not owner or not repo:
        return host, ""
    return host, f"{owner}/{repo}"


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
        include_sample_title=True,
    )
    days = [d for d in plan.get("days", []) if not d.get("skip_reason")]
    domain_project_counts = {
        str(k): list(v)
        for k, v in (plan.get("domain_project_counts", {}) or {}).items()
        if isinstance(k, str) and isinstance(v, list)
    }
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
            try:
                fallback_decisions = _build_guided_decisions(
                    fallback_days,
                    project_names,
                    domain_project_counts=domain_project_counts,
                )
            except KeyboardInterrupt:
                console.print("[yellow]Cancelled before writing config.[/yellow]")
                raise typer.Exit(code=0)
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
    try:
        decisions = _build_guided_decisions(
            days,
            project_names,
            domain_project_counts=domain_project_counts,
        )
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled before writing config.[/yellow]")
        raise typer.Exit(code=0)
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
