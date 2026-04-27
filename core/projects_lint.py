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
    severity: str = "warn"


def lint_projects_payload(payload: dict[str, Any]) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    term_to_projects: dict[str, list[tuple[str, str, str]]] = {}
    repo_path_terms: list[tuple[str, str]] = []
    enabled_projects: list[dict[str, Any]] = []
    for project in payload.get("projects", []):
        if not isinstance(project, dict):
            continue
        if project.get("enabled", True) is False:
            continue
        enabled_projects.append(project)

    for project in enabled_projects:
        name = str(project.get("name", "")).strip()
        customer = str(project.get("customer") or "").strip().lower()
        canonical = str(project.get("canonical_project") or name).strip().lower()
        for term in project.get("match_terms", []) or []:
            clean = str(term).strip().lower()
            if not clean:
                continue
            term_to_projects.setdefault(clean, []).append((name, customer, canonical))
            if _is_repo_path_term(clean):
                repo_path_terms.append((name, _normalize_repo_path_term(clean)))
            if clean in HIGH_RISK_TERMS:
                warnings.append(
                    LintWarning(
                        code="broad-term",
                        message=f"Project '{name}' uses high-risk broad term '{clean}'.",
                    )
                )

    for term, entries in sorted(term_to_projects.items()):
        uniq_names = sorted({name for name, _customer, _canonical in entries if name})
        uniq_customers = {customer for _name, customer, _canonical in entries if customer}
        uniq_canonicals = {canonical for _name, _customer, canonical in entries if canonical}
        # Allowed overlap inside one customer namespace (parent + subprojects).
        # If no customer is set at all, treat it as cross-namespace risk and warn.
        if len(uniq_names) > 1 and (len(uniq_customers) > 1 or not uniq_customers):
            severity = "review" if _looks_like_intentional_overlap(term, uniq_names, uniq_canonicals) else "warn"
            warnings.append(
                LintWarning(
                    code="overlap-term",
                    message=f"match_terms overlap: '{term}' is present in {', '.join(uniq_names)}.",
                    severity=severity,
                )
            )
    warnings.extend(_repo_path_overlap_warnings(repo_path_terms))
    return warnings


def _is_repo_path_term(term: str) -> bool:
    return "/" in term or "\\" in term


def _normalize_repo_path_term(term: str) -> str:
    clean = term.replace("\\", "/").strip().lower()
    while "//" in clean:
        clean = clean.replace("//", "/")
    return clean.rstrip("/")


def _repo_path_overlap_warnings(path_terms: list[tuple[str, str]]) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for idx, (left_name, left_path) in enumerate(path_terms):
        if not left_path:
            continue
        for right_name, right_path in path_terms[idx + 1 :]:
            if not right_path or left_name == right_name or left_path == right_path:
                continue
            shorter, longer = sorted((left_path, right_path), key=len)
            if not longer.startswith(f"{shorter}/"):
                continue
            names = tuple(sorted((left_name, right_name)))
            key = (names[0], names[1], shorter)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            warnings.append(
                LintWarning(
                    code="repo-path-overlap",
                    message=(
                        "repo-path overlap: "
                        f"'{shorter}' also matches a nested path across {names[0]}, {names[1]}."
                    ),
                )
            )
    return warnings


def _looks_like_intentional_overlap(term: str, names: list[str], canonicals: set[str]) -> bool:
    if len(canonicals) == 1:
        return True
    clean_term = _compact_token(term)
    compact_names = [_compact_token(name) for name in names]
    if clean_term and any(clean_term == name or clean_term in name for name in compact_names):
        return True
    if "/" in term:
        tail = term.rsplit("/", 1)[-1]
        compact_tail = _compact_token(tail)
        if compact_tail and any(compact_tail == name or compact_tail in name for name in compact_names):
            return True
    return False


def _compact_token(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def lint_projects_config(config_path: Path) -> list[LintWarning]:
    payload = load_projects_config_payload(config_path)
    return lint_projects_payload(payload)

