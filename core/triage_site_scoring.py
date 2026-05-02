"""Chrome top-site style scoring against project profiles (shared by gap triage and CLI)."""

from __future__ import annotations

from dataclasses import dataclass

from core.triage_domain_signals import is_generic_triage_domain


@dataclass(frozen=True)
class DayTopSite:
    domain: str
    visits: int
    share: float
    sample_title: str


@dataclass(frozen=True)
class ProjectSuggestion:
    canonical: str
    score: int
    aliases: list[str]
    explicit_domain_hits: int
    term_hits: int
    alias_or_name_hits: int
    ticket_mode: str
    default_client: str


def score_projects_for_sites(
    profiles: list[dict],
    top_sites: list[DayTopSite],
    *,
    scoring_mode: str = "site-first",
) -> list[ProjectSuggestion]:
    if scoring_mode not in {"balanced", "site-first"}:
        raise ValueError(f"unsupported scoring mode: {scoring_mode}")
    site_counts = {site.domain: site.visits for site in top_sites}
    scores_by_canonical: dict[str, int] = {}
    aliases_by_canonical: dict[str, set[str]] = {}
    explicit_hits_by_canonical: dict[str, int] = {}
    term_hits_by_canonical: dict[str, int] = {}
    alias_hits_by_canonical: dict[str, int] = {}
    ticket_mode_by_canonical: dict[str, str] = {}
    default_client_by_canonical: dict[str, str] = {}
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if not name:
            continue
        canonical = str(profile.get("canonical_project", "")).strip() or name
        ticket_mode_by_canonical.setdefault(canonical, str(profile.get("ticket_mode", "optional")))
        default_client_by_canonical.setdefault(
            canonical,
            str(profile.get("default_client", "")).strip() or str(profile.get("customer", "")).strip() or canonical,
        )
        tracked = [str(url).strip().lower() for url in profile.get("tracked_urls", []) if url]
        terms = [str(term).strip().lower() for term in profile.get("match_terms", []) if term]
        alias_tokens = [str(alias).strip().lower() for alias in profile.get("aliases", []) if alias]
        name_token = canonical.lower()
        score = 0
        for domain, visits in site_counts.items():
            is_generic = is_generic_triage_domain(domain)
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
            tracked_matches = [value for value in tracked if domain in value or value in domain]
            if tracked_matches:
                # Generic domain anchors (e.g. github.com/google.com/claude.ai) are
                # too broad to dominate project scoring on their own.
                exact_generic_mapping = any(value == domain for value in tracked_matches)
                if is_generic and all(is_generic_triage_domain(value) for value in tracked_matches) and not exact_generic_mapping:
                    tracked_matches = []
                else:
                    score += visits * tracked_weight
                    explicit_hits_by_canonical[canonical] = explicit_hits_by_canonical.get(canonical, 0) + 1
                    continue
            if any(term and term in domain for term in terms):
                score += visits * term_weight
                term_hits_by_canonical[canonical] = term_hits_by_canonical.get(canonical, 0) + 1
                continue
            if any(token and token in domain for token in alias_tokens):
                score += visits * alias_weight
                alias_hits_by_canonical[canonical] = alias_hits_by_canonical.get(canonical, 0) + 1
                continue
            if name_token and name_token in domain:
                score += visits * name_weight
                alias_hits_by_canonical[canonical] = alias_hits_by_canonical.get(canonical, 0) + 1
        if score > 0:
            scores_by_canonical[canonical] = scores_by_canonical.get(canonical, 0) + score
            aliases_by_canonical.setdefault(canonical, set()).add(name)
    ranked = sorted(scores_by_canonical.items(), key=lambda item: (-item[1], item[0].lower()))
    return [
        ProjectSuggestion(
            canonical=canonical,
            score=score,
            aliases=sorted(aliases_by_canonical.get(canonical, set())),
            explicit_domain_hits=explicit_hits_by_canonical.get(canonical, 0),
            term_hits=term_hits_by_canonical.get(canonical, 0),
            alias_or_name_hits=alias_hits_by_canonical.get(canonical, 0),
            ticket_mode=ticket_mode_by_canonical.get(canonical, "optional"),
            default_client=default_client_by_canonical.get(canonical, canonical),
        )
        for canonical, score in ranked
    ]
