"""Lint helpers for project config integrity."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import load_projects_config_payload
from core.tracked_url_policy import is_over_broad_tracked_url

HIGH_RISK_TERMS = {
    "koden",
    "formulär",
    "segel",
    "undersöka",
    "anslutning",
    "katalogen",
    "lösenord",
}

# A profile is a "thin slug duplicate" candidate when its name is a repo-leaf
# slug carrying at most this many match_terms while a richer profile already
# covers the same slug. See docs/task-prompts/work-unit-v2-task.md item 2.
THIN_TERM_MAX = 2

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass
class LintWarning:
    code: str
    message: str
    severity: str = "warn"


def lint_projects_payload(payload: dict[str, Any]) -> list[LintWarning]:
    """Return lint warnings for overlap, slug conflicts, thin duplicates, and broad terms."""
    warnings: list[LintWarning] = []
    term_to_projects: dict[str, list[tuple[str, str, str]]] = {}
    repo_path_terms: list[tuple[str, str]] = []
    profile_infos: list[dict[str, Any]] = []
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
        clean_terms = {
            str(t).strip().lower() for t in (project.get("match_terms", []) or []) if str(t).strip()
        }
        profile_infos.append(
            {
                "name": name,
                "name_lc": name.lower(),
                "customer_lc": customer,
                "terms": clean_terms,
                "count": len(clean_terms),
            }
        )
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
        for raw_url in project.get("tracked_urls", []) or []:
            url = str(raw_url).strip()
            if not url:
                continue
            if is_over_broad_tracked_url(url):
                warnings.append(
                    LintWarning(
                        code="broad-tracked-url",
                        message=(
                            f"Project '{name}' uses over-broad tracked_urls entry '{url}'. "
                            "Remove it or narrow to a specific chat/session URL."
                        ),
                    )
                )

    for term, entries in sorted(term_to_projects.items()):
        uniq_names = sorted({name for name, _customer, _canonical in entries if name})
        uniq_customers = {customer for _name, customer, _canonical in entries if customer}
        uniq_canonicals = {canonical for _name, _customer, canonical in entries if canonical}
        # A repo-slug term mapped to two *explicit* customers will mis-bucket hours
        # at invoice time — the highest-signal config bug. Flag it distinctly and
        # suppress the generic overlap-term to avoid double-reporting.
        if (
            len(uniq_names) > 1
            and len(uniq_customers) > 1
            and (_is_repo_path_term(term) or ("-" in term and _looks_like_slug(term)))
        ):
            warnings.append(
                LintWarning(
                    code="slug-customer-conflict",
                    message=(
                        f"slug '{term}' maps to different customers ({', '.join(sorted(uniq_customers))}) "
                        f"across {', '.join(uniq_names)} — hours will mis-bucket. Attach the anchor to one "
                        "line and remove the duplicate."
                    ),
                )
            )
            continue
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
    warnings.extend(_thin_slug_duplicate_warnings(profile_infos))
    warnings.extend(_repo_path_overlap_warnings(repo_path_terms))
    return warnings


def _is_repo_path_term(term: str) -> bool:
    return "/" in term or "\\" in term


def _normalize_repo_path_term(term: str) -> str:
    clean = term.replace("\\", "/").strip().lower()
    while "//" in clean:
        clean = clean.replace("//", "/")
    return clean.rstrip("/")


def _looks_like_slug(value: str) -> bool:
    """True for a repo-leaf-style token (lowercase, no spaces, e.g. ``portal-repo``)."""
    v = str(value or "").strip()
    return bool(v) and len(v) >= 3 and v == v.lower() and " " not in v and bool(_SLUG_RE.match(v))


def _repo_leaf(term: str) -> str:
    """Last path segment of a term (``acme/portal-repo`` → ``portal-repo``)."""
    norm = _normalize_repo_path_term(term) if _is_repo_path_term(term) else str(term).strip().lower()
    return norm.rsplit("/", 1)[-1]


def _thin_slug_duplicate_warnings(profile_infos: list[dict[str, Any]]) -> list[LintWarning]:
    """Flag a slug-named profile with ≤THIN_TERM_MAX terms that a richer profile already covers.

    The thin profile steals classification for a repo slug another line already
    owns. Fix: attach the anchor to the richer line and remove the thin duplicate.
    """
    warnings: list[LintWarning] = []
    for thin in profile_infos:
        slug = thin["name_lc"]
        if not _looks_like_slug(thin["name"]) or thin["count"] > THIN_TERM_MAX:
            continue
        for other in profile_infos:
            if other["name_lc"] == slug or other["count"] <= thin["count"]:
                continue
            covers = slug in other["terms"] or any(_repo_leaf(t) == slug for t in other["terms"])
            if not covers:
                continue
            message = (
                f"thin slug duplicate: '{thin['name']}' (≤{THIN_TERM_MAX} terms) duplicates slug "
                f"'{slug}' already covered by '{other['name']}' — attach the anchor to '{other['name']}' "
                f"and remove '{thin['name']}'."
            )
            if not thin["customer_lc"] or thin["customer_lc"] == slug:
                message += " It also has no distinct customer (defaults to the line name)."
            warnings.append(LintWarning(code="thin-slug-duplicate", message=message))
            break
    return warnings


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
    if clean_term and _matching_name_count(clean_term, compact_names) >= 2:
        return True
    if "/" in term:
        tail = term.rsplit("/", 1)[-1]
        compact_tail = _compact_token(tail)
        if compact_tail and _matching_name_count(compact_tail, compact_names) >= 2:
            return True
    return False


def _matching_name_count(term: str, names: list[str]) -> int:
    return sum(1 for name in names if term == name or term in name)


def _compact_token(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def lint_projects_config(config_path: Path) -> list[LintWarning]:
    payload = load_projects_config_payload(config_path)
    return lint_projects_payload(payload)

