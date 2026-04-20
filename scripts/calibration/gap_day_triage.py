#!/usr/bin/env python3
"""Show day-level top-site context for unexplained gap triage."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from collectors.chrome import (
    chrome_history_path,
    chrome_time_range,
    query_chrome,
)
from core.config import load_profiles
from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    load_projects_config_payload,
    save_projects_config_payload,
)
from core.report_service import CHROME_EPOCH_DELTA_US

GENERIC_DOMAINS = {
    "google.com",
    "github.com",
    "id.atlassian.com",
    "home.atlassian.com",
    "atlassian.net",
    "mail.google.com",
}


@dataclass(frozen=True)
class DayTopSite:
    domain: str
    visits: int
    share: float
    sample_title: str


def load_gap_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if "days" not in payload:
        raise ValueError(f"{path} missing required key: days")
    return payload


def day_gap_row(payload: dict, day: str) -> dict:
    for row in payload.get("days", []):
        if str(row.get("day")) == day:
            return row
    raise ValueError(f"No gap row found for day: {day}")


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower().strip()
    except Exception:
        return ""
    if host.startswith("www."):
        return host[4:]
    return host


def summarize_day_sites(rows: list[tuple[int, str, str]], *, limit: int = 5) -> list[DayTopSite]:
    if not rows:
        return []
    counts: Counter[str] = Counter()
    sample_titles: dict[str, str] = {}
    for _visit_time_cu, url, title in rows:
        domain = _extract_domain(url)
        if not domain:
            continue
        counts[domain] += 1
        if domain not in sample_titles:
            sample_titles[domain] = (title or "").strip()
    if not counts:
        return []
    total = sum(counts.values())
    out: list[DayTopSite] = []
    for domain, visits in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        out.append(
            DayTopSite(
                domain=domain,
                visits=visits,
                share=visits / total,
                sample_title=sample_titles.get(domain, ""),
            )
        )
    return out


def _domain_is_generic(domain: str) -> bool:
    value = domain.lower().strip()
    if not value:
        return False
    if value in GENERIC_DOMAINS:
        return True
    return any(value.endswith(f".{root}") for root in GENERIC_DOMAINS)


def score_projects_for_sites(
    profiles: list[dict],
    top_sites: list[DayTopSite],
    *,
    scoring_mode: str = "site-first",
) -> list[tuple[str, int, list[str]]]:
    if scoring_mode not in {"balanced", "site-first"}:
        raise ValueError(f"unsupported scoring mode: {scoring_mode}")
    site_counts = {site.domain: site.visits for site in top_sites}
    scores_by_canonical: dict[str, int] = {}
    aliases_by_canonical: dict[str, set[str]] = {}
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if not name:
            continue
        canonical = str(profile.get("canonical_project", "")).strip() or name
        tracked = [str(url).strip().lower() for url in profile.get("tracked_urls", []) if url]
        terms = [str(term).strip().lower() for term in profile.get("match_terms", []) if term]
        alias_tokens = [str(alias).strip().lower() for alias in profile.get("aliases", []) if alias]
        name_token = canonical.lower()
        score = 0
        for domain, visits in site_counts.items():
            is_generic = _domain_is_generic(domain)
            if scoring_mode == "site-first":
                tracked_weight = 8
                term_weight = 1 if not is_generic else 0
                alias_weight = 1 if not is_generic else 0
                name_weight = 1 if not is_generic else 0
            else:
                tracked_weight = 6
                term_weight = 1 if is_generic else 2
                alias_weight = max(1, visits // 2) if is_generic else visits
                name_weight = max(1, visits // 2) if is_generic else visits
            if any(domain in value or value in domain for value in tracked):
                # Explicit domain anchors from --map should dominate generic inference.
                score += visits * tracked_weight
                continue
            if any(term and term in domain for term in terms):
                score += visits * term_weight
                continue
            if any(token and token in domain for token in alias_tokens):
                score += visits * alias_weight
                continue
            if name_token and name_token in domain:
                score += visits * name_weight
        if score > 0:
            scores_by_canonical[canonical] = scores_by_canonical.get(canonical, 0) + score
            aliases_by_canonical.setdefault(canonical, set()).add(name)
    ranked = sorted(scores_by_canonical.items(), key=lambda item: (-item[1], item[0].lower()))
    return [(canonical, score, sorted(aliases_by_canonical.get(canonical, set()))) for canonical, score in ranked]


def fetch_chrome_rows_for_day(day: str, *, home: Path) -> list[tuple[int, str, str]]:
    local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    day_start = datetime.combine(datetime.fromisoformat(day).date(), time.min, tzinfo=local_tz)
    day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)
    dt_from_cu, dt_to_cu = chrome_time_range(day_start, day_end, CHROME_EPOCH_DELTA_US)
    history_path = chrome_history_path(home)
    return query_chrome(
        history_path,
        where_clause="1=1",
        dt_from_cu=dt_from_cu,
        dt_to_cu=dt_to_cu,
    )


def render_report(
    *,
    day: str,
    gap_row: dict,
    top_sites: list[DayTopSite],
    project_suggestions: list[tuple[str, int, list[str]]],
    projects_config: str,
) -> str:
    unexplained = float(gap_row.get("unexplained_screen_time_hours", 0.0))
    estimated = float(gap_row.get("estimated_hours", 0.0))
    screen = float(gap_row.get("screen_time_hours", 0.0))
    lines = [
        "Gap Day Triage (Internal)",
        f"- Day: {day}",
        f"- Estimated hours: {estimated:.2f}",
        f"- Screen time hours: {screen:.2f}",
        f"- Unexplained screen time hours: {unexplained:.2f}",
        "",
        "Top sites (Chrome visits):",
    ]
    if top_sites:
        for site in top_sites:
            title_suffix = f" | sample: {site.sample_title[:60]}" if site.sample_title else ""
            lines.append(
                f"- {site.domain}: {site.visits} visits ({site.share * 100:.1f}%){title_suffix}"
            )
    else:
        lines.append("- None (no Chrome history rows for this day)")
    lines.extend(["", "Suggested projects to review:"])
    if project_suggestions:
        for canonical, score, aliases in project_suggestions[:5]:
            alias_suffix = f" | aliases: {', '.join(aliases)}" if aliases else ""
            lines.append(f"- {canonical} (signal score: {score}){alias_suffix}")
        target = project_suggestions[0][0]
    else:
        lines.append("- No strong match from current profile rules")
        target = "<project-name>"
    lines.extend(
        [
            "",
            "Next action (record mapping):",
            f"- gittan suggest-rules --project \"{target}\" --from {day} --to {day} --projects-config {projects_config}",
            "- If needed, update project terms/URLs with: gittan projects --config timelog_projects.json",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show top sites and mapping hints for one gap-analysis day."
    )
    parser.add_argument("--day", required=True, help="Target day (YYYY-MM-DD)")
    parser.add_argument(
        "--gap-json",
        default="out/reconciliation/screen_time_gap.json",
        help="Path to screen_time_gap.json payload",
    )
    parser.add_argument(
        "--projects-config",
        default="timelog_projects.json",
        help="Path to project profile config",
    )
    parser.add_argument("--limit", type=int, default=5, help="Number of top sites to print")
    parser.add_argument(
        "--scoring-mode",
        default="site-first",
        choices=["balanced", "site-first"],
        help="Scoring strategy for project suggestions (default: site-first).",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        help="Apply mapping as domain=ProjectName (repeatable). Writes tracked_urls to projects config.",
    )
    parser.add_argument(
        "--allow-create-projects",
        action="store_true",
        help="Allow --map to create missing project names (default: fail on unknown names).",
    )
    return parser


def parse_map_assignments(raw_assignments: list[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for raw in raw_assignments:
        text = str(raw).strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"Invalid --map value (expected domain=ProjectName): {raw}")
        domain, project = text.split("=", 1)
        domain = domain.strip().lower()
        project = project.strip()
        if not domain or not project:
            raise ValueError(f"Invalid --map value (expected domain=ProjectName): {raw}")
        parsed.append((domain, project))
    return parsed


def apply_domain_mappings(
    projects_config: Path,
    assignments: list[tuple[str, str]],
    *,
    allow_create_projects: bool = False,
) -> tuple[int, int]:
    if not assignments:
        return 0, 0
    payload = load_projects_config_payload(projects_config)
    existing_names = {
        str(project.get("name", "")).strip().lower()
        for project in payload.get("projects", [])
        if isinstance(project, dict) and str(project.get("name", "")).strip()
    }
    unknown = sorted(
        {
            project
            for _domain, project in assignments
            if project.strip().lower() not in existing_names
        }
    )
    if unknown and not allow_create_projects:
        raise ValueError(
            "Unknown project name(s) in --map: "
            + ", ".join(unknown)
            + ". Use existing names from timelog_projects.json "
            + "or pass --allow-create-projects."
        )
    backup_projects_config_if_exists(projects_config)
    created_count = 0
    applied_count = 0
    for domain, project in assignments:
        _rule_type, _rule_value, created = apply_rule_to_project(
            payload,
            project_name=project,
            rule_type="tracked_urls",
            rule_value=domain,
        )
        applied_count += 1
        if created:
            created_count += 1
    save_projects_config_payload(projects_config, payload)
    return applied_count, created_count


def load_profiles_for_projects_config(projects_config: str) -> list[dict]:
    profiles, _config_path, _workspace = load_profiles(
        projects_config,
        SimpleNamespace(project="default-project", keywords="", email=""),
    )
    return profiles


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = load_gap_payload(Path(args.gap_json).expanduser())
    row = day_gap_row(payload, args.day)
    chrome_rows = fetch_chrome_rows_for_day(args.day, home=Path.home())
    top_sites = summarize_day_sites(chrome_rows, limit=max(1, int(args.limit)))
    assignments = parse_map_assignments(args.map)
    if assignments:
        projects_config_path = Path(args.projects_config).expanduser()
        applied_count, created_count = apply_domain_mappings(
            projects_config_path,
            assignments,
            allow_create_projects=bool(args.allow_create_projects),
        )
        print(
            f"Applied {applied_count} mapping(s) to {projects_config_path}"
            + (f" ({created_count} new project(s) created)." if created_count else ".")
        )
    profiles = load_profiles_for_projects_config(args.projects_config)
    suggestions = score_projects_for_sites(
        profiles,
        top_sites,
        scoring_mode=str(args.scoring_mode),
    )
    print(
        render_report(
            day=args.day,
            gap_row=row,
            top_sites=top_sites,
            project_suggestions=suggestions,
            projects_config=args.projects_config,
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
