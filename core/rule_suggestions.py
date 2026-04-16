"""Heuristic A/B rule suggestions from uncategorized clusters (v1)."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from core.domain import classify_project
from core.uncategorized_review import UncategorizedCluster

COMMON_DOMAINS = frozenset(
    {
        "google.com",
        "www.google.com",
        "youtube.com",
        "mail.google.com",
        "gmail.com",
        "slack.com",
        "notion.so",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "facebook.com",
        "reddit.com",
    }
)

ROUTE_FEATURES = frozenset(
    {
        "checkout",
        "pricing",
        "subscription",
        "subscriptions",
        "dashboard",
        "settings",
        "billing",
        "invoice",
        "payment",
        "signup",
        "login",
        "admin",
        "api",
        "cart",
        "order",
        "onboarding",
        "trial",
    }
)

CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")
DOMAIN_RE = re.compile(r"([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})")
META_NOISE_TERMS = frozenset(
    {
        "commit",
        "post-merge",
        "first-pass",
        "cherry-picking",
        "click-to-run",
        "branch/sync",
        "root-level",
        "fast-path",
        "end-to-end",
    }
)
META_NOISE_PREFIXES = (
    "docs/",
    "scripts/",
    "core/",
    "tests/",
)
NOISY_MATCH_TERM_SOURCES = frozenset({"timelog.md", "timelog"})

@dataclass(frozen=True)
class RuleSuggestion:
    rule_type: str
    rule_value: str
    cluster_count: int
    source: str
    samples: tuple[str, ...]
    note: str

    def as_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["samples"] = list(self.samples)
        return d

    @staticmethod
    def from_cluster(cluster: UncategorizedCluster, note: str) -> RuleSuggestion:
        samples = tuple(cluster.samples[:3])
        value = _normalized_rule_value(cluster.rule_type, cluster.rule_value)
        return RuleSuggestion(
            rule_type=cluster.rule_type,
            rule_value=value,
            cluster_count=cluster.count,
            source=cluster.source,
            samples=samples,
            note=note,
        )


def ab_suggestions_state_path(config_path: Path) -> Path:
    return config_path.parent / f"{config_path.stem}.ab-suggestions.json"


def normalize_payload_projects_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("projects", [])
    if isinstance(raw, dict):
        return [v for v in raw.values() if isinstance(v, dict)]
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]
    raise ValueError("payload['projects'] must be a list or dict of project objects")


def _other_project_signals(profiles: list[dict[str, Any]], target_name: str) -> set[str]:
    signals: set[str] = set()
    tnorm = target_name.strip().lower()
    for profile in profiles:
        name = str(profile.get("name", "")).strip().lower()
        if not name or name == tnorm:
            continue
        signals.add(name)
        for term in profile.get("match_terms") or []:
            if term:
                signals.add(str(term).lower())
        for url in profile.get("tracked_urls") or []:
            if url:
                signals.add(str(url).lower())
    return signals


def _target_existing_rules(profile: dict[str, Any] | None) -> set[tuple[str, str]]:
    if not profile:
        return set()
    out: set[tuple[str, str]] = set()
    for term in profile.get("match_terms") or []:
        out.add(("match_terms", _normalized_rule_value("match_terms", str(term))))
    for url in profile.get("tracked_urls") or []:
        out.add(("tracked_urls", _normalized_rule_value("tracked_urls", str(url))))
    return out


def _find_target_profile(profiles: list[dict[str, Any]], project_name: str) -> dict[str, Any] | None:
    tnorm = project_name.strip().lower()
    for profile in profiles:
        if str(profile.get("name", "")).strip().lower() == tnorm:
            return profile
    return None


def _ambiguous_value(rule_type: str, value: str, others: set[str]) -> bool:
    v = _normalized_rule_value(rule_type, value)
    if not v:
        return True
    if v in others:
        return True
    for sig in others:
        if len(v) >= 4 and (v in sig or sig in v):
            return True
    if rule_type == "tracked_urls":
        host = v
        for sig in others:
            if "." in host and host in sig:
                return True
    return False


def _strong_term_shape(term: str) -> bool:
    return "-" in term or "/" in term


def _has_route_token(term: str) -> bool:
    parts = re.split(r"[^a-z0-9]+", term.lower())
    return bool(ROUTE_FEATURES & set(parts))


def _domain_is_common(domain: str) -> bool:
    host = domain.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host in COMMON_DOMAINS


def _rule_key(cluster: UncategorizedCluster) -> tuple[str, str]:
    if cluster.rule_type == "match_terms":
        return ("match_terms", _normalized_rule_value("match_terms", cluster.rule_value))
    return ("tracked_urls", _normalized_rule_value("tracked_urls", cluster.rule_value))


def _cluster_applicable(cluster: UncategorizedCluster, existing: set[tuple[str, str]]) -> bool:
    return _rule_key(cluster) not in existing


def _note_for_cluster(cluster: UncategorizedCluster, tier: str) -> str:
    if cluster.rule_type == "tracked_urls":
        return f"domain anchor ({tier})"
    if tier == "safe":
        return "repeated specific term (lower cross-project ambiguity)"
    if tier == "medium":
        return "medium-confidence repeated term"
    return "route/feature-style token"


def _strip_control_chars(text: str) -> str:
    return CONTROL_CHARS_RE.sub("", text)


def _sanitize_tracked_url_value(value: str) -> str:
    raw = _strip_control_chars(value.strip().lower())
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    candidate = parsed.netloc or parsed.path
    candidate = _strip_control_chars(candidate).strip()
    match = DOMAIN_RE.search(candidate)
    if match:
        return match.group(1)
    match = DOMAIN_RE.search(raw)
    if match:
        return match.group(1)
    return candidate


def _normalized_rule_value(rule_type: str, value: str) -> str:
    if rule_type == "tracked_urls":
        return _sanitize_tracked_url_value(value)
    return _strip_control_chars(value.strip().lower())


def _is_meta_noise_term(term: str) -> bool:
    t = term.strip().lower()
    if not t:
        return True
    if t in META_NOISE_TERMS:
        return True
    if t.startswith(META_NOISE_PREFIXES):
        return True
    if t.endswith(".md") or t.endswith(".py"):
        return True
    if "timelog" in t:
        return True
    return False


def split_ab_suggestions(
    clusters: Iterable[UncategorizedCluster],
    profiles: list[dict[str, Any]],
    project_name: str,
) -> tuple[list[RuleSuggestion], list[RuleSuggestion]]:
    """Return (option_a, option_b) where B is a superset of A."""
    target = _find_target_profile(profiles, project_name)
    existing = _target_existing_rules(target)
    others = _other_project_signals(profiles, project_name)

    safe: list[RuleSuggestion] = []
    broad_only: list[RuleSuggestion] = []
    assigned: set[tuple[str, str]] = set()

    def key_for_suggestion(rule_type: str, rule_value: str) -> tuple[str, str]:
        if rule_type == "match_terms":
            return ("match_terms", _normalized_rule_value("match_terms", rule_value))
        return ("tracked_urls", _normalized_rule_value("tracked_urls", rule_value))

    for cluster in clusters:
        if not _cluster_applicable(cluster, existing):
            continue
        rv = _normalized_rule_value(cluster.rule_type, cluster.rule_value)
        ck = _rule_key(cluster)
        if ck in assigned:
            continue

        if cluster.rule_type == "tracked_urls":
            if _ambiguous_value("tracked_urls", rv, others):
                continue
            common = _domain_is_common(rv)
            if cluster.count >= 2 or (cluster.count >= 1 and not common):
                sug = RuleSuggestion.from_cluster(cluster, _note_for_cluster(cluster, "safe"))
                assigned.add(ck)
                safe.append(sug)
            elif cluster.count >= 1 and common:
                sug = RuleSuggestion.from_cluster(
                    cluster,
                    "single-event on common domain (broad only)",
                )
                assigned.add(ck)
                broad_only.append(sug)
            continue

        term = rv.lower()
        if cluster.source.strip().lower() in NOISY_MATCH_TERM_SOURCES:
            continue
        if _is_meta_noise_term(term):
            continue
        if _ambiguous_value("match_terms", term, others):
            continue

        if cluster.count >= 2 and (_strong_term_shape(term) or len(term) >= 8):
            sug = RuleSuggestion.from_cluster(cluster, _note_for_cluster(cluster, "safe"))
            assigned.add(ck)
            safe.append(sug)
            continue

        if cluster.count >= 2 and len(term) >= 4:
            sug = RuleSuggestion.from_cluster(cluster, _note_for_cluster(cluster, "medium"))
            assigned.add(ck)
            broad_only.append(sug)
            continue

        if cluster.count >= 1 and (_strong_term_shape(term) or _has_route_token(term)):
            sug = RuleSuggestion.from_cluster(cluster, _note_for_cluster(cluster, "broad"))
            assigned.add(ck)
            broad_only.append(sug)

    merged_b = list(safe)
    b_keys = {key_for_suggestion(s.rule_type, s.rule_value) for s in safe}
    for s in broad_only:
        k = key_for_suggestion(s.rule_type, s.rule_value)
        if k in b_keys:
            continue
        b_keys.add(k)
        merged_b.append(s)
    return safe, merged_b


def augment_profiles_with_rules(
    profiles: list[dict[str, Any]],
    project_name: str,
    rules: list[RuleSuggestion],
) -> list[dict[str, Any]]:
    out = copy.deepcopy(profiles)
    target = _find_target_profile(out, project_name)
    if target is None:
        target = {
            "name": project_name.strip(),
            "match_terms": [project_name.strip().lower()],
            "tracked_urls": [],
        }
        out.append(target)

    for rule in rules:
        if rule.rule_type == "match_terms":
            terms = {t.lower() for t in target.get("match_terms") or [] if t}
            terms.add(_normalized_rule_value("match_terms", rule.rule_value))
            target["match_terms"] = sorted(terms)
        elif rule.rule_type == "tracked_urls":
            urls = {str(u).strip() for u in target.get("tracked_urls") or [] if u}
            cleaned = _normalized_rule_value("tracked_urls", rule.rule_value)
            if cleaned:
                urls.add(cleaned)
            target["tracked_urls"] = sorted(urls)
    return out


def preview_suggestion_impact(
    uncategorized_events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    project_name: str,
    rules: list[RuleSuggestion],
    *,
    gap_minutes: int,
    min_session_minutes: int,
    min_session_passive_minutes: int,
    exclude_keywords: list[str],
    uncategorized_label: str = "Uncategorized",
) -> tuple[int, float, int]:
    """Return (matched_events, matched_hours, uncategorized_delta)."""
    if not rules:
        return 0, 0.0, 0
    augmented = augment_profiles_with_rules(profiles, project_name, rules)
    matched: list[dict[str, Any]] = []
    for event in uncategorized_events:
        if event.get("project") != uncategorized_label:
            continue
        detail = str(event.get("detail") or "")
        assigned = classify_project(detail, augmented, uncategorized_label)
        if assigned == project_name:
            matched.append(event)

    if not matched:
        return 0, 0.0, 0

    from core.report_service import estimate_hours_by_day, group_by_day

    days = group_by_day(matched, exclude_keywords=exclude_keywords)
    per_day = estimate_hours_by_day(
        days,
        gap_minutes=gap_minutes,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
    )
    hours = sum(day["hours"] for day in per_day.values())
    return len(matched), round(hours, 3), -len(matched)


def write_suggestions_state(
    path: Path,
    *,
    projects_config: str,
    target_project: str,
    uncategorized_total: int,
    option_previews: dict[str, Any],
) -> None:
    option_a = option_previews.get("A")
    option_b = option_previews.get("B")
    if not isinstance(option_a, dict) or not isinstance(option_b, dict):
        raise ValueError("option_previews must include both 'A' and 'B' preview dicts")
    payload = {
        "version": 1,
        "projects_config": projects_config,
        "target_project": target_project,
        "uncategorized_total": uncategorized_total,
        "options": {"A": option_a, "B": option_b},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_suggestions_state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rules_from_state_option(state: dict[str, Any], option: str) -> list[RuleSuggestion]:
    block = state.get("options", {}).get(str(option).upper())
    if not block:
        return []
    out: list[RuleSuggestion] = []
    for raw in block.get("rules", []):
        if not isinstance(raw, dict):
            continue
        rule_type = str(raw.get("rule_type", "")).strip()
        rule_value = str(raw.get("rule_value", "")).strip()
        if rule_type not in {"match_terms", "tracked_urls"} or not rule_value:
            continue
        out.append(
            RuleSuggestion(
                rule_type=rule_type,
                rule_value=rule_value,
                cluster_count=int(raw.get("cluster_count", 0)),
                source=str(raw.get("source", "")),
                samples=tuple(raw.get("samples") or [])[:3],
                note=str(raw.get("note", "")),
            )
        )
    return out
