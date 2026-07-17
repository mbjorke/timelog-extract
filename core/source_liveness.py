"""Silent-source watchdog: alarm when a previously active source flatlines (GH-366).

Twice in one week (#345, #363) a collector silently produced zero events while
``gittan doctor`` still reported "Logs readable" — reachability, not liveness.
This module detects the alarm condition: a source that was recently active
produces zero events in the report window while sibling sources show activity.

Precision rule (real-data tuned): the *report* alarm fires only when a source in
the **same application family** is active while this source flatlines — the
exact #345/#363 signature (Cursor busy, "Cursor (agent)" silent means the app is
running but one of its log streams stopped). "You did not open tool X today" is
normal life, not an anomaly; that broader gone-quiet view lives in the
``gittan doctor`` liveness rows instead, where it informs without alarming.

Baselines, in order of preference:

1. **Shadow evidence log** (``~/.gittan/evidence``, GH-254) — per-source activity
   on days before the report window. Dates compare on the record's UTC
   ``observed_at`` day; the (rare) local-midnight skew only shifts a baseline
   day, never invents activity.
2. **Window-internal fallback** (no store required) — for windows spanning at
   least two calendar days, "yesterday vs today" relative to the report's
   ``dt_to`` date: a source active on the preceding calendar day but silent on
   the window end day while a family sibling is not.

A genuinely idle window (no source produced anything) never alarms, and neither
do disabled/opt-in-off sources, coverage comparators, or content-derived
sources (WordPress, Lovable (web), …) whose zero just means "no matching URLs".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.sources import COVERAGE_COMPARATOR, SOURCE_ROLES

#: Days of shadow-log history considered "recent" for the baseline.
LOOKBACK_DAYS = 14
#: A source must have been active on at least this many distinct baseline days.
MIN_BASELINE_DAYS_ACTIVE = 2
#: ... and its last activity must fall within this many days before the window.
MAX_SILENT_GAP_DAYS = 3

#: Sources that never emit timeline events (presence comparators) — no liveness.
_NEVER_ALARM = frozenset(
    name for name, role in SOURCE_ROLES.items() if role == COVERAGE_COMPARATOR
)

#: Content-derived sources: their events are parsed out of another source's
#: data (Chrome history URLs/titles). Zero events means "no matching content",
#: not a broken log stream — if the parent breaks, the parent alarms.
CONTENT_DERIVED_SOURCES = frozenset(
    {"WordPress", "Lovable (web)", "Claude.ai (web)", "Gemini (web)"}
)

#: Derived sources: skip when the parent collector is disabled/opt-in off.
DERIVED_SOURCE_PARENT = {
    "Cursor (agent)": "Cursor",
    "WordPress": "Chrome",
    "Lovable (web)": "Chrome",
    "Claude.ai (web)": "Chrome",
    "Gemini (web)": "Chrome",
}

#: Application families: log streams of the same running app. The report alarm
#: fires only when a family sibling is active while this stream is silent —
#: the app demonstrably ran, but one of its streams stopped producing evidence
#: (the #345/#363 signature). Sources without siblings can only mean "not used
#: today", which is doctor-row information, not a report warning.
SOURCE_FAMILY = {
    "Cursor": "cursor",
    "Cursor (agent)": "cursor",
    "Cursor checkpoints": "cursor",
    "Claude Desktop": "claude-desktop",
    "Claude Desktop (Code)": "claude-desktop",
}


def _family_siblings(source: str) -> List[str]:
    family = SOURCE_FAMILY.get(source)
    if family is None:
        return []
    return [
        name
        for name, fam in SOURCE_FAMILY.items()
        if fam == family and name != source
    ]


@dataclass
class SilentSourceFinding:
    """One previously active source that produced nothing when siblings did."""

    source: str
    last_active: Optional[str]  # YYYY-MM-DD, best known
    baseline: str  # "shadow-log" | "window"
    baseline_days_active: int
    scope: str  # "window" (zero in whole window) | "last-day" (fallback)


def _event_day(event: Dict[str, Any]) -> Optional[str]:
    ts = event.get("timestamp")
    if isinstance(ts, datetime):
        return ts.date().isoformat()
    return None


def events_by_source_day(events: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Per-source, per-day (ISO date) event counts."""
    out: Dict[str, Dict[str, int]] = {}
    for event in events or []:
        source = str(event.get("source") or "")
        day = _event_day(event)
        if not source or not day:
            continue
        per_day = out.setdefault(source, {})
        per_day[day] = per_day.get(day, 0) + 1
    return out


def shadow_baseline_by_source(
    window_start: date,
    *,
    home: Optional[Path] = None,
    lookback_days: int = LOOKBACK_DAYS,
) -> Dict[str, Dict[str, Any]]:
    """Per-source recent-activity baseline from the shadow evidence log.

    Counts records observed on days in ``[window_start - lookback, window_start)``.
    Returns ``{}`` when the store does not exist (watchdog falls back to the
    window-internal comparison).
    """
    from core.evidence_store import events_dir, evidence_base_dir, read_records

    ev_dir = events_dir(evidence_base_dir(home))
    if not ev_dir.is_dir():
        return {}
    start = window_start - timedelta(days=lookback_days)
    # Enumerate every calendar month the lookback touches (a >2-month lookback
    # would otherwise skip the middle months' files).
    months = set()
    cursor = start.replace(day=1)
    while cursor <= window_start:
        months.add(cursor.isoformat()[:7])
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    baseline: Dict[str, Dict[str, Any]] = {}
    for month, record in read_records(ev_dir):
        if month not in months:
            continue
        day_str = str(record.get("observed_at") or "")[:10]
        if not day_str:
            continue
        try:
            day = date.fromisoformat(day_str)
        except ValueError:
            continue
        if not (start <= day < window_start):
            continue
        source = str(record.get("source") or "")
        if not source:
            continue
        entry = baseline.setdefault(source, {"days": set(), "events": 0})
        entry["days"].add(day_str)
        entry["events"] += 1
    return {
        source: {
            "days_active": len(entry["days"]),
            "last_active": max(entry["days"]),
            "events": entry["events"],
        }
        for source, entry in baseline.items()
    }


def _source_disabled(source: str, collector_status: Dict[str, Dict[str, Any]]) -> bool:
    """True when the source (or the collector it derives from) is disabled."""
    for name in (source, DERIVED_SOURCE_PARENT.get(source)):
        if not name:
            continue
        status = collector_status.get(name)
        if status is not None and status.get("enabled") is False:
            return True
    return False


def _shadow_findings(
    window_counts: Dict[str, Dict[str, int]],
    baseline: Dict[str, Dict[str, Any]],
    collector_status: Dict[str, Dict[str, Any]],
    window_start: date,
) -> List[SilentSourceFinding]:
    findings: List[SilentSourceFinding] = []
    recent_floor = (window_start - timedelta(days=MAX_SILENT_GAP_DAYS)).isoformat()
    for source, info in sorted(baseline.items()):
        if source in _NEVER_ALARM or source in CONTENT_DERIVED_SOURCES:
            continue
        if source in window_counts:
            continue
        if not any(sibling in window_counts for sibling in _family_siblings(source)):
            continue  # app not demonstrably running — doctor-row info, not an alarm
        if info["days_active"] < MIN_BASELINE_DAYS_ACTIVE:
            continue
        if info["last_active"] < recent_floor:
            continue
        if _source_disabled(source, collector_status):
            continue
        findings.append(
            SilentSourceFinding(
                source=source,
                last_active=info["last_active"],
                baseline="shadow-log",
                baseline_days_active=info["days_active"],
                scope="window",
            )
        )
    return findings


def _window_fallback_findings(
    window_counts: Dict[str, Dict[str, int]],
    collector_status: Dict[str, Dict[str, Any]],
    *,
    window_end: date,
    window_start: date,
) -> List[SilentSourceFinding]:
    """No-store baseline: calendar yesterday vs window end inside a multi-day window.

    Uses the report's ``dt_to`` date as the silent day (not the latest eventful
    day), so an idle final day — common when ``dt_to`` is "now" — still
    compares against the preceding calendar day.
    """
    if window_end <= window_start:
        return []
    last_day = window_end.isoformat()
    prev_day = (window_end - timedelta(days=1)).isoformat()
    findings: List[SilentSourceFinding] = []
    for source, per_day in sorted(window_counts.items()):
        if source in _NEVER_ALARM or source in CONTENT_DERIVED_SOURCES:
            continue
        if per_day.get(last_day):
            continue
        if not per_day.get(prev_day):
            continue
        if not any(
            window_counts.get(sibling, {}).get(last_day)
            for sibling in _family_siblings(source)
        ):
            continue  # app not demonstrably running on the silent day
        if _source_disabled(source, collector_status):
            continue
        findings.append(
            SilentSourceFinding(
                source=source,
                last_active=prev_day,
                baseline="window",
                baseline_days_active=len(per_day),
                scope="last-day",
            )
        )
    return findings


def detect_silent_sources(
    all_events: List[Dict[str, Any]],
    collector_status: Dict[str, Dict[str, Any]],
    dt_from: datetime,
    dt_to: Optional[datetime] = None,
    *,
    home: Optional[Path] = None,
    lookback_days: int = LOOKBACK_DAYS,
) -> List[SilentSourceFinding]:
    """Detect previously active sources that went silent in the report window."""
    window_counts = events_by_source_day(all_events)
    if not window_counts:
        return []  # genuinely idle window — no alarm
    window_start = dt_from.date()
    baseline = shadow_baseline_by_source(
        window_start, home=home, lookback_days=lookback_days
    )
    if baseline:
        return _shadow_findings(window_counts, baseline, collector_status, window_start)
    # Prefer explicit window end; fall back to latest event day only when callers
    # omit dt_to (legacy / unit helpers).
    if dt_to is not None:
        window_end = dt_to.date()
    else:
        event_days = sorted(
            {day for per_day in window_counts.values() for day in per_day}
        )
        if len(event_days) < 2:
            return []
        window_end = date.fromisoformat(event_days[-1])
    return _window_fallback_findings(
        window_counts,
        collector_status,
        window_end=window_end,
        window_start=window_start,
    )


def apply_liveness_to_collector_status(
    collector_status: Dict[str, Dict[str, Any]],
    findings: List[SilentSourceFinding],
) -> None:
    """Mark silent sources in ``collector_status`` (JSON payload / extension).

    Keys are event-source labels; a sub-source without its own collector entry
    (e.g. "Cursor (agent)" inside the "Cursor" collector) gets one added so the
    anomaly is addressable by consumers.
    """
    for finding in findings:
        status = collector_status.setdefault(
            finding.source, {"enabled": True, "reason": "", "events": 0}
        )
        status["liveness"] = {
            "state": "silent",
            "scope": finding.scope,
            "baseline": finding.baseline,
            "last_active": finding.last_active,
            "baseline_days_active": finding.baseline_days_active,
        }


def silent_source_warning_lines(findings: List[SilentSourceFinding]) -> List[str]:
    """Human-readable warning lines for the report footer."""
    lines: List[str] = []
    for finding in findings:
        if finding.scope == "window":
            lines.append(
                f"Silent source: {finding.source} produced 0 events in this window "
                f"but was active {finding.baseline_days_active} of the last "
                f"{LOOKBACK_DAYS} days (last {finding.last_active}). "
                f"If you worked in it, evidence may be dropping — run `gittan doctor`."
            )
        else:
            lines.append(
                f"Silent source: {finding.source} has 0 events on the window's last day "
                f"but was active the day before ({finding.last_active}). "
                f"If you worked in it, evidence may be dropping — run `gittan doctor`."
            )
    return lines


def apply_silent_source_watchdog(report: Any, *, home: Optional[Path] = None) -> List[SilentSourceFinding]:
    """Run detection on a ``ReportPayload``-like object and patch its collector_status.

    Idempotent — safe to call from both the CLI and the engine-API path.
    """
    findings = detect_silent_sources(
        getattr(report, "all_events", []) or [],
        report.collector_status,
        report.dt_from,
        getattr(report, "dt_to", None),
        home=home,
    )
    apply_liveness_to_collector_status(report.collector_status, findings)
    return findings
