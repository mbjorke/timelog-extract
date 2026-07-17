"""Work-unit v2 spike classifier: signals → WorkUnit → customer_ref.

Builds an in-memory WorkUnit view from v1 profiles (no schema change). Thin
slug-only duplicates collapse into the richer canonical unit so classification
returns the existing line key — never a new slug-only profile name.

See docs/decisions/work-unit-v2-architecture.md §4 and §8, and backlog item 1
in docs/task-prompts/work-unit-v2-task.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.domain import (
    GENERIC_TOOL_TERMS,
    _is_path_like_term,
    _matches_term,
    _prepare_haystack_and_word_set,
)
from core.projects_lint import THIN_TERM_MAX, _looks_like_slug, _repo_leaf

PRIMARY_REPO = "repo"
PRIMARY_TICKET = "ticket"
PRIMARY_NAME = "name"

_TICKET_RE_PREFIXES = ("gh-", "jira-", "ticket-")


@dataclass(frozen=True)
class WorkUnit:
    """In-memory work unit for the spike classifier (not a persisted schema)."""

    line_key: str
    customer_ref: str
    primary: str
    signals: tuple[str, ...]
    source_names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def signal_count(self) -> int:
        return len(self.signals)


def _infer_primary(name: str) -> str:
    clean = str(name or "").strip()
    lower = clean.lower()
    if any(lower.startswith(p) for p in _TICKET_RE_PREFIXES):
        return PRIMARY_TICKET
    if _looks_like_slug(clean):
        return PRIMARY_REPO
    return PRIMARY_NAME


def _profile_signals(profile: Dict[str, Any]) -> list[str]:
    signals: list[str] = []
    seen: set[str] = set()
    for term in profile.get("match_terms") or []:
        clean = str(term).strip().lower()
        if clean and clean not in seen:
            seen.add(clean)
            signals.append(clean)
    for url in profile.get("tracked_urls") or []:
        fragment = str(url).strip().lower()
        if fragment and fragment not in seen:
            seen.add(fragment)
            signals.append(fragment)
    name = str(profile.get("name") or "").strip().lower()
    if name and name not in seen:
        signals.append(name)
    return signals


def _customer_ref(profile: Dict[str, Any]) -> str:
    name = str(profile.get("name") or "").strip()
    raw = profile.get("customer")
    if raw is None or not str(raw).strip():
        return name
    return str(raw).strip()


def _term_count(profile: Dict[str, Any]) -> int:
    return len([t for t in (profile.get("match_terms") or []) if str(t).strip()])


def _richness_score(profile: Dict[str, Any]) -> int:
    """Classifier signal richness excluding the profile name (every profile has one).

    Counts distinct ``match_terms`` and ``tracked_urls`` the same way
    ``_profile_signals`` builds the unit, so URL-only richness can beat a
    thin slug that only has equal term count.
    """
    name = str(profile.get("name") or "").strip().lower()
    return len([sig for sig in _profile_signals(profile) if sig != name])


def _profile_covers_slug(profile: Dict[str, Any], slug: str) -> bool:
    slug_lc = slug.lower()
    terms = [str(t).strip().lower() for t in (profile.get("match_terms") or []) if str(t).strip()]
    if slug_lc in terms:
        return True
    return any(_repo_leaf(t) == slug_lc for t in terms)


def _find_canonical_for_thin(
    thin: Dict[str, Any],
    profiles: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Richer profile that already covers this thin slug-named profile's name."""
    slug = str(thin.get("name") or "").strip()
    if not _looks_like_slug(slug) or _term_count(thin) > THIN_TERM_MAX:
        return None
    thin_score = _richness_score(thin)
    best: Optional[Dict[str, Any]] = None
    best_score = thin_score
    for other in profiles:
        if other is thin:
            continue
        other_name = str(other.get("name") or "").strip()
        if other_name.lower() == slug.lower():
            continue
        score = _richness_score(other)
        if score <= thin_score:
            continue
        if not _profile_covers_slug(other, slug):
            continue
        if score > best_score:
            best = other
            best_score = score
    return best


def build_work_units(profiles: Sequence[Dict[str, Any]]) -> list[WorkUnit]:
    """Map v1 profiles to WorkUnits, collapsing thin slug duplicates into richer lines.

    Collapsed thin profiles contribute their signals to the canonical unit; they
    do not appear as separate line keys. Customer is always taken from the
    canonical profile's ``customer`` field (never inferred from a matched signal).
    """
    enabled = [p for p in profiles if isinstance(p, dict) and p.get("enabled", True) is not False]
    collapse_into: Dict[str, str] = {}
    extra_signals: Dict[str, list[str]] = {}

    for profile in enabled:
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        canonical = _find_canonical_for_thin(profile, enabled)
        if canonical is None:
            continue
        canon_name = str(canonical.get("name") or "").strip()
        collapse_into[name] = canon_name
        bucket = extra_signals.setdefault(canon_name, [])
        for sig in _profile_signals(profile):
            if sig not in bucket:
                bucket.append(sig)

    units: list[WorkUnit] = []
    for profile in enabled:
        name = str(profile.get("name") or "").strip()
        if not name or name in collapse_into:
            continue
        signals = _profile_signals(profile)
        for extra in extra_signals.get(name, []):
            if extra not in signals:
                signals.append(extra)
        source_names = (name,)
        # Record which thin names folded in (for scorecards / debugging).
        folded = tuple(sorted(src for src, dest in collapse_into.items() if dest == name))
        if folded:
            source_names = (name,) + folded
        units.append(
            WorkUnit(
                line_key=name,
                customer_ref=_customer_ref(profile),
                primary=_infer_primary(name),
                signals=tuple(signals),
                source_names=source_names,
            )
        )
    return units


def _signal_weight(signal: str) -> tuple[float, bool]:
    """Return (weight, is_specific) for a matched signal."""
    if signal in GENERIC_TOOL_TERMS:
        return 0.25, False
    if _is_path_like_term(signal) or "/" in signal or signal.startswith("http"):
        return 2.0, True
    if "." in signal and " " not in signal:
        # host-like / url fragment
        return 2.0, True
    return 1.0, True


_LAST_UNITS_DATA: tuple[Any, Any, Any] | None = None


def _compile_units_index(
    units: Sequence[WorkUnit],
) -> tuple[
    dict[str, list[tuple[int, float, bool, int]]],
    list[tuple[str, list[tuple[int, float, bool, int]]]],
    dict[str, list[tuple[int, float, bool, int]]],
]:
    """Index units by signal for fast lookup.

    Returns:
        fast_signals: Map of alphanumeric signals to (unit_idx, weight, is_specific, length)
        slow_signals: List of (signal, impacts) for non-alphanumeric or path-like signals
        all_signals: Combined map for all signals
    """
    signal_to_impacts: dict[str, list[tuple[int, float, bool, int]]] = {}

    for i, unit in enumerate(units):
        for signal in unit.signals:
            if not signal:
                continue
            if signal not in signal_to_impacts:
                signal_to_impacts[signal] = []
            weight, is_specific = _signal_weight(signal)
            signal_to_impacts[signal].append((i, weight, is_specific, len(signal)))

    fast_signals: dict[str, list[tuple[int, float, bool, int]]] = {}
    slow_signals: list[tuple[str, list[tuple[int, float, bool, int]]]] = []

    for signal, impacts in signal_to_impacts.items():
        if signal.isalnum() and not _is_path_like_term(signal):
            fast_signals[signal] = impacts
        else:
            slow_signals.append((signal, impacts))

    return fast_signals, slow_signals, signal_to_impacts


def _get_compiled_units_index(units: Sequence[WorkUnit]) -> tuple[
    dict[str, list[tuple[int, float, bool, int]]],
    list[tuple[str, list[tuple[int, float, bool, int]]]],
    dict[str, list[tuple[int, float, bool, int]]],
]:
    """Caching wrapper to avoid re-compiling the index for the same units list.

    Always fingerprints content (same pattern as ``domain._get_compiled_index``)
    so in-place list mutation cannot reuse a stale compiled index. Do not add an
    identity-only early return — that bypasses invalidation for mutable lists.
    """
    global _LAST_UNITS_DATA

    fingerprint = (len(units), tuple((u.line_key, u.signals) for u in units))
    if (
        _LAST_UNITS_DATA is None
        or _LAST_UNITS_DATA[0] is not units
        or _LAST_UNITS_DATA[1] != fingerprint
    ):
        _LAST_UNITS_DATA = (units, fingerprint, _compile_units_index(units))
    return _LAST_UNITS_DATA[2]


def classify_work_unit(
    text: str,
    units: Sequence[WorkUnit],
    fallback: str,
) -> str:
    """Score text against WorkUnit signals; return line_key or fallback.

    Customer is never chosen here — callers look up ``customer_ref`` from the
    winning unit. Tie-break: higher specific-signal score, then more distinct
    matched signals, then longer match length, then fewer generic hits.
    """
    if not text:
        return fallback

    fast_signals, slow_signals, all_signals = _get_compiled_units_index(units)
    haystack_with_variants, word_set = _prepare_haystack_and_word_set(text.lower())

    matched_signals = set()
    # 1. Fast path: alphanumeric signals that are definitely in the text's word set.
    for signal in fast_signals.keys() & word_set:
        matched_signals.add(signal)

    # 2. Slow path: path-like or special-char signals.
    # Only check them if the signal appears as a substring in the haystack.
    for signal, _ in slow_signals:
        if signal in haystack_with_variants:
            if _matches_term(signal, haystack_with_variants, word_set=word_set):
                matched_signals.add(signal)

    if not matched_signals:
        return fallback

    num_units = len(units)
    scores = [0.0] * num_units
    specifics = [0] * num_units
    generics = [0] * num_units
    lens = [0] * num_units
    distincts = [0] * num_units

    # 3. Single-pass scoring: accumulate rank components for all matching units.
    for signal in matched_signals:
        for idx, weight, is_specific, sig_len in all_signals[signal]:
            scores[idx] += weight
            lens[idx] += sig_len
            distincts[idx] += 1
            if is_specific:
                specifics[idx] += 1
            else:
                generics[idx] += 1

    best_key = fallback
    # Rank: (weighted, specific_hits, distinct_signals, match_len, -generic_hits)
    best_rank = (0.0, 0, 0, 0, 0)

    for i in range(num_units):
        if specifics[i] > 0 or scores[i] >= 1.0:
            rank = (scores[i], specifics[i], distincts[i], lens[i], -generics[i])
            if rank > best_rank:
                best_rank = rank
                best_key = units[i].line_key

    return best_key


def customer_for_line(units: Sequence[WorkUnit], line_key: str, fallback: str = "") -> str:
    for unit in units:
        if unit.line_key == line_key:
            return unit.customer_ref
    return fallback


def make_work_unit_classify_fn(
    fallback: str = "Uncategorized",
) -> Callable[[str, List[Dict[str, Any]]], str]:
    """Return a ``(text, profiles) -> line_key`` callable for the report seam."""

    cache: Dict[int, list[WorkUnit]] = {}

    def classify(text: str, profiles: List[Dict[str, Any]]) -> str:
        key = id(profiles)
        units = cache.get(key)
        if units is None:
            units = build_work_units(profiles)
            cache[key] = units
        return classify_work_unit(text, units, fallback)

    return classify


# Public alias used by TimelogRunOptions / report_service.
ATTRIBUTION_CLASSIFIER_V1 = "v1"
ATTRIBUTION_CLASSIFIER_WORK_UNIT_V2 = "work_unit_v2"
_WORK_UNIT_V2_ALIASES = frozenset(
    {
        ATTRIBUTION_CLASSIFIER_WORK_UNIT_V2,
        "work-unit-v2",
        "v2",
    }
)
_ALLOWED_ATTRIBUTION_CLASSIFIERS = frozenset(
    {ATTRIBUTION_CLASSIFIER_V1} | _WORK_UNIT_V2_ALIASES
)


def resolve_attribution_classify_fn(
    mode: str,
    *,
    fallback: str = "Uncategorized",
    v1_fn: Callable[[str, List[Dict[str, Any]]], str] | None = None,
) -> Callable[[str, List[Dict[str, Any]]], str]:
    """Select v1 or work_unit_v2 classify callable from a mode string.

    Empty / missing mode defaults to v1. Unknown non-empty values raise
    ``ValueError`` so typos cannot silently disable the spike classifier.
    """
    normalized = str(mode or ATTRIBUTION_CLASSIFIER_V1).strip().lower() or (
        ATTRIBUTION_CLASSIFIER_V1
    )
    if normalized in _WORK_UNIT_V2_ALIASES:
        return make_work_unit_classify_fn(fallback)
    if normalized == ATTRIBUTION_CLASSIFIER_V1:
        if v1_fn is not None:
            return v1_fn

        def _v1(text: str, profiles: List[Dict[str, Any]]) -> str:
            from core.domain import classify_project

            return classify_project(text, profiles, fallback)

        return _v1
    allowed = ", ".join(sorted(_ALLOWED_ATTRIBUTION_CLASSIFIERS))
    raise ValueError(
        f"Unknown attribution_classifier {mode!r}; expected one of: {allowed}"
    )
