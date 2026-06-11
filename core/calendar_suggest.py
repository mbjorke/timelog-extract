"""Suggest project profiles from calendar event titles (onboarding, P7).

People who track time in a calendar encode the project as a *code* in the event
title — e.g. ``HÅ-DAA standup``, ``EASE-DAA review``, ``KidneySign proteomics
data``, ``AXOR – OneFlow``. This module extracts those codes heuristically and
proposes project profiles for the ones not already covered by an existing
profile's ``match_terms``.

It is **suggestion-only**: it never writes config. The output is meant for human
review (the heuristic is ranked by frequency).

Known limitation: only *distinctive* codes are detected — hyphenated
(``HÅ-DAA``), CamelCase (``KidneySign``), ALL-CAPS (``AXOR``), or dotted
(``immuniverse.bio``). A bare single-word project name like ``Strike`` is
indistinguishable from an ordinary word, so it is intentionally not proposed
(better a missed suggestion than proposing every capitalized word). Such projects
can still be added by hand.

See docs/product/calendar-beat-the-parser-backlog.md (P7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

# Tokens that look like a project code:
#   - hyphenated with an uppercase letter:  HÅ-DAA, EASE-DAA
#   - CamelCase (lower then upper):         KidneySign, OneFlow
#   - ALL-CAPS, length >= 3:                AXOR, STRIKE
#   - dotted domain-ish:                    immuniverse.bio
_HYPHEN_CODE = re.compile(r"^[^\W\d_]*[A-ZÅÄÖ][^\W_]*-[^\W_]+$", re.UNICODE)
_CAMEL_CODE = re.compile(r"^[^\W\d_]*[a-zåäö][A-ZÅÄÖ][^\W_]*$", re.UNICODE)
_ALLCAPS_CODE = re.compile(r"^[A-ZÅÄÖ][A-ZÅÄÖ0-9]{2,}$", re.UNICODE)
_DOTTED_CODE = re.compile(r"^[^\W\d_][\w]*\.[a-z]{2,}$", re.UNICODE)

# Strip surrounding punctuation a calendar title commonly carries.
_STRIP = " \t:,;.!?()[]{}\"'«»–—-"


def _looks_like_code(token: str) -> bool:
    t = token.strip(_STRIP)
    if len(t) < 3:
        return False
    return bool(
        _HYPHEN_CODE.match(t)
        or _CAMEL_CODE.match(t)
        or _ALLCAPS_CODE.match(t)
        or _DOTTED_CODE.match(t)
    )


def extract_codes(title: str) -> List[str]:
    """Return the code-like tokens in ``title`` (original case, de-punctuated)."""
    codes: List[str] = []
    for raw in str(title or "").split():
        if _looks_like_code(raw):
            codes.append(raw.strip(_STRIP))
    return codes


@dataclass(frozen=True)
class ProjectSuggestion:
    code: str                      # the project code as it appears in titles
    count: int                     # how many titles contained it
    examples: Tuple[str, ...] = field(default_factory=tuple)  # sample titles

    def as_profile(self) -> Dict[str, object]:
        """A ready-to-paste project profile stub for this code."""
        return {"name": self.code, "match_terms": [self.code]}

    def as_json_dict(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "count": self.count,
            "examples": list(self.examples),
            "suggested_profile": self.as_profile(),
        }


def _covered_terms(existing_profiles: Sequence[Dict[str, object]]) -> set:
    """Lowercased match_terms already configured, so we only suggest new codes."""
    covered = set()
    for profile in existing_profiles or []:
        for term in (profile.get("match_terms") or []):
            t = str(term).strip().lower()
            if t:
                covered.add(t)
    return covered


def suggest_projects_from_titles(
    titles: Iterable[str],
    existing_profiles: Sequence[Dict[str, object]] = (),
    *,
    min_count: int = 1,
    max_examples: int = 3,
) -> List[ProjectSuggestion]:
    """Rank candidate project codes found in ``titles`` that are not yet covered.

    Codes already present (case-insensitively) in any existing profile's
    ``match_terms`` are skipped. Results are sorted by frequency (desc), then
    code (asc) for deterministic output.
    """
    covered = _covered_terms(existing_profiles)
    counts: Dict[str, int] = {}
    examples: Dict[str, List[str]] = {}
    canonical: Dict[str, str] = {}  # lowercased code -> first-seen original case

    for title in titles:
        for code in extract_codes(title):
            key = code.lower()
            if key in covered:
                continue
            canonical.setdefault(key, code)
            counts[key] = counts.get(key, 0) + 1
            if len(examples.setdefault(key, [])) < max_examples:
                examples[key].append(str(title).strip())

    suggestions = [
        ProjectSuggestion(
            code=canonical[key],
            count=counts[key],
            examples=tuple(examples[key]),
        )
        for key in counts
        if counts[key] >= min_count
    ]
    suggestions.sort(key=lambda s: (-s.count, s.code.lower()))
    return suggestions
