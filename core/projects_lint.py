"""Lint helpers for project config integrity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import load_projects_config_payload


HIGH_RISK_TERMS = {
    "koden",
    "formulär",
    "segel",
    "undersöka",
    "anslutning",
    "katalogen",
    "lösenord",
}


@dataclass
class LintWarning:
    code: str
    message: str


def lint_projects_payload(payload: dict[str, Any]) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    term_to_projects: dict[str, list[tuple[str, str]]] = {}
    enabled_projects: list[dict[str, Any]] = []
    for project in payload.get("projects", []):
        if not isinstance(project, dict):
            continue
        if project.get("enabled", True) is False:
            continue
        enabled_projects.append(project)

    for project in enabled_projects:
        name = str(project.get("name", "")).strip()
        customer = str(project.get("customer", "")).strip().lower()
        for term in project.get("match_terms", []) or []:
            clean = str(term).strip().lower()
            if not clean:
                continue
            term_to_projects.setdefault(clean, []).append((name, customer))
            if clean in HIGH_RISK_TERMS:
                warnings.append(
                    LintWarning(
                        code="broad-term",
                        message=f"Project '{name}' uses high-risk broad term '{clean}'.",
                    )
                )

    for term, entries in sorted(term_to_projects.items()):
        uniq_names = sorted({name for name, _customer in entries if name})
        uniq_customers = {customer for _name, customer in entries if customer}
        # Allowed overlap inside one customer namespace (parent + subprojects).
        # If no customer is set at all, treat it as cross-namespace risk and warn.
        if len(uniq_names) > 1 and (len(uniq_customers) > 1 or not uniq_customers):
            warnings.append(
                LintWarning(
                    code="overlap-term",
                    message=f"match_terms overlap: '{term}' is present in {', '.join(uniq_names)}.",
                )
            )
    return warnings


def lint_projects_config(config_path: Path) -> list[LintWarning]:
    payload = load_projects_config_payload(config_path)
    return lint_projects_payload(payload)

