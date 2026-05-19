"""Typer command: map domains to projects across a date range."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional
import questionary
import typer
from questionary import Choice

from core.cli_app import app
from core.cli_date_range import resolve_date_window
from core.cli_triage import build_triage_plan_dict
from core.cli_triage_apply import apply_triage_decisions_payload
from core.config import default_projects_config_option, load_projects_config_payload, normalize_profile
from core.triage_domain_signals import (
    canonical_domain_key,
    is_generic_triage_domain,
    merged_history_entries_for_canonical,
    tracked_fragment_matches_domain,
)
from core.triage_site_scoring import DayTopSite, score_projects_for_sites

_DECISIONS_SCHEMA_VERSION = 1


def _is_history_dominant(
    *,
    domain: str,
    project_name: str,
    domain_project_counts: dict[str, list[dict[str, Any]]],
) -> bool:
    history = merged_history_entries_for_canonical(domain, domain_project_counts)
    total = sum(int(item.get("events", 0) or 0) for item in history)
    if total <= 0:
        return False
    target = sum(
        int(item.get("events", 0) or 0)
        for item in history
        if str(item.get("project", "")).strip().lower() == project_name.lower()
    )
    return target >= 3 and (target / total) >= 0.7


def _load_triage_profiles(projects_config: str) -> list[dict[str, Any]]:
    payload = load_projects_config_payload(Path(projects_config))
    profiles: list[dict[str, Any]] = []
    for raw in payload.get("projects", []):
        if not isinstance(raw, dict) or not bool(raw.get("enabled", True)):
            continue
        profiles.append(normalize_profile(raw))
    return profiles


def _resolve_project_name(profiles: list[dict[str, Any]], canonical: str) -> str:
    key = str(canonical or "").strip().lower()
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if name.lower() == key:
            return name
    for profile in profiles:
        c = str(profile.get("canonical_project", "")).strip()
        if c.lower() == key:
            return str(profile.get("name", "")).strip() or c
    return str(canonical or "").strip()


def _uniform_resolved_project_across_days(plan: dict[str, Any]) -> Optional[str]:
    """If every non-skipped triage day agrees on the same top suggestion, return it."""
    names: list[str] = []
    for day in plan.get("days", []) or []:
        if day.get("skip_reason"):
            continue
        p = str(day.get("resolved_project_for_top_suggestion") or "").strip()
        if p:
            names.append(p)
    if len(names) < 2:
        return None
    first = names[0]
    if all(n == first for n in names):
        return first
    return None


def _best_profile_for_tracked_domain(domain: str, profiles: list[dict[str, Any]]) -> Optional[str]:
    """Pick the project whose tracked_urls best matches this host (longest fragment wins)."""
    best_len = 0
    best_name: Optional[str] = None
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if not name:
            continue
        for raw in profile.get("tracked_urls") or []:
            if not raw:
                continue
            if not tracked_fragment_matches_domain(domain, str(raw)):
                continue
            frag = str(raw).strip().lower()
            if len(frag) > best_len:
                best_len = len(frag)
                best_name = name
    return best_name


def _profile_for_github_repo_hint(repo_hint: str, profiles: list[dict[str, Any]]) -> Optional[str]:
    rh = str(repo_hint or "").strip().lower()
    if not rh or "/" not in rh:
        return None
    best_len = 0
    best_name: Optional[str] = None
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if not name:
            continue
        for raw in profile.get("tracked_urls") or []:
            u = str(raw).strip().lower()
            if rh in u and len(u) > best_len:
                best_len = len(u)
                best_name = name
    return best_name


def _predict_project_for_domain(
    *,
    domain: str,
    visits: int,
    sample_title: str,
    profiles: list[dict[str, Any]],
    scoring_mode: str,
) -> Optional[dict[str, Any]]:
    suggestions = score_projects_for_sites(
        profiles,
        [
            DayTopSite(
                domain=domain,
                visits=max(1, int(visits)),
                share=1.0,
                sample_title=str(sample_title or ""),
            )
        ],
        scoring_mode=scoring_mode,
    )
    if not suggestions:
        return None
    top = suggestions[0]
    return {
        "project_name": _resolve_project_name(profiles, top.canonical),
        "explicit_domain_hits": int(getattr(top, "explicit_domain_hits", 0) or 0),
        "term_hits": int(getattr(top, "term_hits", 0) or 0),
        "alias_or_name_hits": int(getattr(top, "alias_or_name_hits", 0) or 0),
        "score": int(getattr(top, "score", 0) or 0),
    }


def _resolve_top_project_for_domain(
    *,
    plan: dict[str, Any],
    domain: str,
    info: dict[str, Any],
    fallback_project: str,
    predicted: Optional[dict[str, Any]],
    profiles: list[dict[str, Any]],
    domain_project_counts: dict[str, list[dict[str, Any]]],
) -> tuple[str, bool, bool]:
    """Returns (project_name, mapped_from_signal, needs_manual_project)."""
    uniform_day = _uniform_resolved_project_across_days(plan)
    repo_hint = str(info.get("repo_hint", "") or "").strip()

    tracked_name = _best_profile_for_tracked_domain(domain, profiles)
    github_name = None
    if canonical_domain_key(domain) == "github.com":
        github_name = _profile_for_github_repo_hint(repo_hint, profiles)

    trusted_predict = False
    if predicted:
        trusted_predict = int(predicted.get("explicit_domain_hits", 0) or 0) > 0 or int(
            predicted.get("term_hits", 0) or 0
        ) > 0

    history = merged_history_entries_for_canonical(domain, domain_project_counts)
    history_name = str(history[0].get("project", "")).strip() if history else ""
    history_total = sum(int(item.get("events", 0) or 0) for item in history)
    history_top_events = int(history[0].get("events", 0) or 0) if history else 0
    history_use = False
    if history_name and history_total > 0:
        ratio = history_top_events / history_total
        second_events = int(history[1].get("events", 0) or 0) if len(history) > 1 else 0
        if ratio >= 0.65 and (history_top_events >= second_events + 2 or second_events == 0):
            if uniform_day and history_name == uniform_day:
                history_use = False
            else:
                history_use = True

    if trusted_predict and predicted:
        return str(predicted.get("project_name") or "").strip(), True, False
    if tracked_name:
        return tracked_name, True, False
    if github_name:
        return github_name, True, False
    if history_use and history_name:
        return history_name, True, False

    if uniform_day and fallback_project == uniform_day:
        return "", False, True

    return fallback_project, False, False


def build_domain_project_candidates(
    plan: dict[str, Any],
    *,
    min_votes: int,
    profiles: list[dict[str, Any]],
    scoring_mode: str,
) -> list[dict[str, Any]]:
    by_domain: dict[str, dict[str, Any]] = {}
    domain_project_counts = {
        str(k): list(v)
        for k, v in (plan.get("domain_project_counts", {}) or {}).items()
        if isinstance(k, str) and isinstance(v, list)
    }
    for day in plan.get("days", []):
        if day.get("skip_reason"):
            continue
        project_name = str(day.get("resolved_project_for_top_suggestion") or "").strip()
        if not project_name:
            continue
        for site in day.get("top_sites", []):
            domain_raw = str(site.get("domain", "")).strip()
            if not domain_raw:
                continue
            domain = canonical_domain_key(domain_raw)
            if not domain:
                continue
            info = by_domain.setdefault(
                domain,
                {
                    "domain_visits": 0,
                    "project_votes": {},
                    "sample_title": "",
                    "repo_hint": "",
                },
            )
            info["domain_visits"] = int(info["domain_visits"]) + int(site.get("visits", 1) or 1)
            votes = info["project_votes"]
            votes[project_name] = int(votes.get(project_name, 0)) + 1
            if not info["sample_title"] and str(site.get("sample_title", "")).strip():
                info["sample_title"] = str(site.get("sample_title", "")).strip()
            if not info["repo_hint"] and str(site.get("repo_hint", "")).strip():
                info["repo_hint"] = str(site.get("repo_hint", "")).strip()

    out: list[dict[str, Any]] = []
    for domain, info in by_domain.items():
        ranked = sorted(info["project_votes"].items(), key=lambda item: (-item[1], item[0]))
        fallback_project, top_votes = ranked[0]
        predicted = _predict_project_for_domain(
            domain=domain,
            visits=int(info.get("domain_visits", 1) or 1),
            sample_title=str(info.get("sample_title", "") or ""),
            profiles=profiles,
            scoring_mode=scoring_mode,
        )
        top_project, mapped_signal, needs_manual = _resolve_top_project_for_domain(
            plan=plan,
            domain=domain,
            info=info,
            fallback_project=fallback_project,
            predicted=predicted,
            profiles=profiles,
            domain_project_counts=domain_project_counts,
        )
        total_votes = sum(int(v) for _, v in ranked)
        dominance = (top_votes / total_votes) if total_votes else 0.0
        history_check_name = str(top_project or fallback_project).strip()
        history_dominant = _is_history_dominant(
            domain=domain,
            project_name=history_check_name,
            domain_project_counts=domain_project_counts,
        )
        if top_votes < int(min_votes) and not history_dominant:
            continue
        generic = is_generic_triage_domain(domain)
        signal_hits = 0
        if predicted:
            signal_hits = int(predicted.get("explicit_domain_hits", 0)) + int(predicted.get("term_hits", 0))
        low_confidence = generic and not (
            history_dominant or bool(info["repo_hint"]) or signal_hits > 0 or mapped_signal
        )
        ambiguous_split = False
        if len(ranked) >= 2:
            second_votes = int(ranked[1][1])
            ambiguous_split = second_votes >= int(top_votes) - 1 and int(top_votes) > 0
        out.append(
            {
                "domain": domain,
                "project_name": top_project,
                "votes": int(top_votes),
                "total_votes": int(total_votes),
                "dominance": float(dominance),
                "sample_title": str(info["sample_title"] or ""),
                "repo_hint": str(info["repo_hint"] or ""),
                "history_dominant": history_dominant,
                "low_confidence": low_confidence,
                "ambiguous_split": ambiguous_split,
                "mapped_from_domain_signal": mapped_signal,
                "needs_manual_project": needs_manual,
            }
        )
    out.sort(key=lambda item: (-item["votes"], -item["dominance"], item["domain"]))
    return out


def _candidate_choice(item: dict[str, Any]) -> Choice:
    domain = str(item["domain"])
    project_name = str(item["project_name"])
    if bool(item.get("needs_manual_project")) or not project_name.strip():
        label = f"{domain} -> (no auto project) — add tracked_urls / evidence first"
        return Choice(title=label, value=domain, disabled="No confident project mapping")
    votes = int(item["votes"])
    dominance = float(item["dominance"])
    title_preview = str(item.get("sample_title", "")).replace("\n", " ").strip()
    if len(title_preview) > 50:
        title_preview = title_preview[:47].rstrip() + "..."
    repo_hint = str(item.get("repo_hint", "")).strip()
    parts = [f"{domain} -> {project_name}", f"votes: {votes}", f"share: {dominance:.0%}"]
    if repo_hint:
        parts.append(repo_hint)
    if title_preview:
        parts.append(title_preview)
    label = " — ".join(parts)
    if bool(item.get("ambiguous_split")):
        label = f"{label} — [ambiguous: competing projects]"
    if bool(item.get("low_confidence")):
        return Choice(title=f"{label} — [low confidence: generic domain]", value=domain, disabled="Needs stronger signal")
    return Choice(title=label, value=domain)


def _decisions_payload(decisions: list[dict[str, str]]) -> dict[str, Any]:
    return {"schema_version": _DECISIONS_SCHEMA_VERSION, "decisions": decisions}


@app.command("triage-domains")
def triage_domains(
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
    max_days: Annotated[int, typer.Option(help="Max days to scan for domain->project votes")] = 14,
    max_sites: Annotated[int, typer.Option(help="Top sites per day")] = 8,
    min_votes: Annotated[int, typer.Option(help="Minimum day votes per domain unless history is dominant")] = 1,
    scoring_mode: Annotated[str, typer.Option(help="balanced or site-first")] = "site-first",
    write_decisions: Annotated[Optional[str], typer.Option("--write-decisions", help="Write decisions JSON to path")] = None,
) -> None:
    """Aggregate domain->project candidates and apply only explicit selections."""
    from rich.console import Console

    from core.cli_deprecation import warn_deprecated_triage_command

    warn_deprecated_triage_command("gittan triage-domains")

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
    profiles = _load_triage_profiles(projects_config)
    candidates = build_domain_project_candidates(
        plan,
        min_votes=min_votes,
        profiles=profiles,
        scoring_mode=scoring_mode,
    )
    if not candidates:
        console.print("[yellow]No domain candidates met the threshold in this range.[/yellow]")
        raise typer.Exit(code=0)
    picked_domains = questionary.checkbox(
        "Select domain -> project mappings to apply:",
        choices=[_candidate_choice(item) for item in candidates],
    ).ask()
    if not picked_domains:
        console.print("[yellow]No domain mappings selected. Nothing to apply.[/yellow]")
        raise typer.Exit(code=0)

    by_domain = {str(item["domain"]): item for item in candidates}
    decisions: list[dict[str, str]] = []
    for domain in picked_domains:
        item = by_domain.get(str(domain))
        if not item:
            continue
        pname = str(item.get("project_name") or "").strip()
        if not pname or item.get("needs_manual_project"):
            continue
        decisions.append(
            {
                "project_name": pname,
                "rule_type": "tracked_urls",
                "rule_value": str(item["domain"]),
            }
        )
    if write_decisions:
        output_path = Path(write_decisions).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(_decisions_payload(decisions), indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]Decisions file written:[/green] {output_path}")

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
    confirmed = questionary.confirm("Apply these domain mappings now?", default=False).ask()
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
    console.print("[green]Domain triage apply complete.[/green]")
