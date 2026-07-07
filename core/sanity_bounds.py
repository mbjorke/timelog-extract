"""Plausibility guardrails for estimated hours (accuracy net).

These are display-only sanity checks, not part of session or billing math. They
exist because a collector defect once collapsed whole days into single ~24h
sessions and CI stayed green (see docs/task-prompts/repo-time-totals-task.md).
The goal is to make implausible output *visible* — never to silently rewrite it.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

# A single continuous work session longer than this is almost certainly a
# session-merge artifact (background telemetry bridging idle gaps), not real work.
MAX_PLAUSIBLE_SESSION_HOURS = 16.0
# A calendar day physically cannot contain more than 24h of work; exceeding it
# means double-counting in allocation.
MAX_HOURS_PER_DAY = 24.0
# Observed hours this far above measured Screen Time signal over-attribution.
OVER_ATTRIBUTION_RATIO = 1.5


def find_implausible_sessions(
    overall_days: Dict[str, Any],
    session_duration_hours_fn: Callable[..., float],
    *,
    min_session_minutes: int,
    min_session_passive_minutes: int,
    threshold_hours: float = MAX_PLAUSIBLE_SESSION_HOURS,
) -> List[Tuple[str, float]]:
    """Return (day, hours) for every session longer than ``threshold_hours``.

    ``session_duration_hours_fn`` matches the 5-arg wrapper the report passes
    (events, start, end, min_session, min_session_passive); the AI-source set is
    already baked into that wrapper.
    """
    flagged: List[Tuple[str, float]] = []
    for day, payload in overall_days.items():
        for session in payload.get("sessions", []):
            start_ts, end_ts, events = session[:3]
            hours = session_duration_hours_fn(
                events,
                start_ts,
                end_ts,
                min_session_minutes,
                min_session_passive_minutes,
            )
            if hours > threshold_hours:
                flagged.append((day, hours))
    return flagged


def day_total_hours(project_reports: Dict[str, Any]) -> Dict[str, float]:
    """Sum allocated project hours per day across all projects."""
    totals: Dict[str, float] = {}
    for days in project_reports.values():
        for day, payload in days.items():
            totals[day] = totals.get(day, 0.0) + float(payload.get("hours", 0.0))
    return totals


def days_exceeding_24h(
    project_reports: Dict[str, Any],
    *,
    cap_hours: float = MAX_HOURS_PER_DAY,
) -> List[Tuple[str, float]]:
    """Return (day, total_hours) for any day whose allocated hours exceed 24h.

    A non-empty result is a hard invariant violation (double-counting), not a
    soft plausibility hint.
    """
    return [
        (day, hours)
        for day, hours in sorted(day_total_hours(project_reports).items())
        if hours > cap_hours + 1e-6
    ]


def over_attribution_ratio(
    observed_hours: float,
    screen_time_hours: float,
) -> Optional[float]:
    """Observed / Screen Time, or None when Screen Time is unavailable."""
    if screen_time_hours <= 0:
        return None
    return observed_hours / screen_time_hours


def plausibility_warnings(
    *,
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    observed_hours: float,
    screen_time_hours: Optional[float],
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
    ratio_threshold: float = OVER_ATTRIBUTION_RATIO,
) -> List[str]:
    """Build human-readable warnings for any plausibility breach. Empty == clean."""
    warnings: List[str] = []

    implausible = find_implausible_sessions(
        overall_days,
        session_duration_hours_fn,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
    )
    if implausible:
        worst_day, worst_h = max(implausible, key=lambda item: item[1])
        warnings.append(
            f"{len(implausible)} session(s) exceed {MAX_PLAUSIBLE_SESSION_HOURS:.0f}h "
            f"(longest {worst_h:.1f}h on {worst_day}) — likely session-merge artifact, "
            f"review before invoicing"
        )

    over_24h = days_exceeding_24h(project_reports)
    if over_24h:
        worst_day, worst_h = max(over_24h, key=lambda item: item[1])
        warnings.append(
            f"{len(over_24h)} day(s) attribute more than 24h "
            f"({worst_h:.1f}h on {worst_day}) — double-counting bug, do not invoice"
        )

    if screen_time_hours is not None and screen_time_hours > 0:
        ratio = over_attribution_ratio(observed_hours, screen_time_hours)
        if ratio is not None and ratio > ratio_threshold:
            warnings.append(
                f"observed (evidenced) {observed_hours:.1f}h is {ratio:.1f}× Screen Time "
                f"{screen_time_hours:.1f}h — possible over-attribution, review before invoicing"
            )

    return warnings
