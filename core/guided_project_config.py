"""Read-only guidance for improving project configuration."""

from __future__ import annotations

from typing import Any

from core.projects_lint import lint_projects_payload


def build_guided_config_plan(
    *,
    projects_payload: dict[str, Any],
    triage_days: list[dict[str, Any]],
    projects_config: str,
) -> dict[str, Any]:
    """Summarize review evidence without proposing config writes."""
    lint_items = [
        {
            "code": warning.code,
            "severity": warning.severity,
            "message": warning.message,
        }
        for warning in lint_projects_payload(projects_payload)
    ]
    return {
        "mode": "evidence-review",
        "projects_config": projects_config,
        "candidates": _build_evidence_candidates(projects_payload, triage_days),
        "config_warnings": lint_items,
        "next_steps": _next_steps(lint_items),
    }


def _build_evidence_candidates(
    projects_payload: dict[str, Any],
    triage_days: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    existing = _existing_tracked_domains(projects_payload)
    for day in triage_days:
        suggested_projects = _suggested_project_names(day)
        repo_hosts = {
            _host_from_tracked_value(str(repo.get("value", "")))
            for repo in day.get("code_repos", []) or []
        }
        repo_hosts.discard("")
        for repo in day.get("code_repos", []) or []:
            value = str(repo.get("value", "")).strip()
            if not value or value.lower() in existing:
                continue
            key = ("code_repo", value.lower())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "candidate_type": "code_repo",
                    "provider": str(repo.get("provider", "")).strip(),
                    "rule_type": "tracked_urls",
                    "value": value,
                    "visits": int(repo.get("visits", 0)),
                    "suggested_projects": suggested_projects,
                    "requires_user_choice": True,
                    "day": day.get("day"),
                }
            )
        for site in day.get("top_sites", []) or []:
            value = str(site.get("domain", "")).strip()
            if not value or value.lower() in existing:
                continue
            if value.lower() in repo_hosts:
                continue
            key = ("domain", value.lower())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "candidate_type": "domain",
                    "rule_type": "tracked_urls",
                    "value": value,
                    "visits": int(site.get("visits", 0)),
                    "share": float(site.get("share", 0.0)),
                    "suggested_projects": suggested_projects,
                    "requires_user_choice": True,
                    "day": day.get("day"),
                }
            )
    return candidates


def _existing_tracked_domains(projects_payload: dict[str, Any]) -> set[str]:
    domains: set[str] = set()
    for project in projects_payload.get("projects", []) or []:
        if not isinstance(project, dict):
            continue
        for value in project.get("tracked_urls", []) or []:
            clean = str(value).strip().lower()
            if clean:
                domains.add(clean)
    return domains


def _host_from_tracked_value(value: str) -> str:
    text = value.lower().strip()
    return text.split("/", 1)[0]


def _suggested_project_names(day: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for suggestion in day.get("suggestions", [])[:3]:
        name = str(suggestion.get("canonical", "")).strip()
        if name and name not in names:
            names.append(name)
    return names


def _next_steps(lint_items: list[dict[str, Any]]) -> list[str]:
    steps: list[str] = []
    steps.append("Choose a project/customer for each evidence candidate before applying any config change.")
    steps.append("Apply only explicit decisions with `gittan triage-apply`; do not pipe triage JSON into config.")
    if any(item["severity"] == "warn" for item in lint_items):
        steps.append("Resolve warn-level project config lint findings before trusting totals.")
    if not steps:
        steps.append("No project config changes suggested for this range.")
    return steps
