"""Helpers for evidence coverage diagnostics in CLI flows."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def build_evidence_snapshot(report: Any) -> Dict[str, Any]:
    source_counts = Counter(str(event.get("source") or "") for event in report.included_events)
    source_counts.pop("", None)
    all_events = list(getattr(report, "all_events", None) or [])
    included = list(getattr(report, "included_events", None) or [])
    excluded_uncategorized = max(0, len(all_events) - len(included))
    observed_hours = float(sum(float(day.get("hours", 0.0) or 0.0) for day in (report.overall_days or {}).values()))
    screen_values = [float(v or 0.0) for v in (report.screen_time_days or {}).values()]
    # Screen Time may be stored as seconds/day (large integers) or hours/day (small floats).
    # Daily wall-clock Screen Time in hours rarely exceeds ~24h; values >> that are seconds.
    if screen_values:
        # Normalize each day independently to avoid one anomalous value skewing all days.
        screen_time_hours = float(sum((v / 3600.0) if v > 48.0 else v for v in screen_values))
    else:
        screen_time_hours = 0.0
    delta_hours = screen_time_hours - observed_hours
    return {
        "observed_hours": observed_hours,
        "screen_time_hours": screen_time_hours,
        "delta_hours": delta_hours,
        "source_counts": dict(source_counts),
        "excluded_uncategorized_events": excluded_uncategorized,
    }


def build_evidence_warnings(snapshot: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    delta = float(snapshot.get("delta_hours", 0.0) or 0.0)
    source_counts = snapshot.get("source_counts") or {}
    active_sources = [src for src, count in source_counts.items() if int(count) > 0]
    chrome_count = int(source_counts.get("Chrome", 0) or 0)
    if delta >= 2.0:
        warnings.append(f"Large Screen Time gap (+{delta:.1f}h) suggests missing evidence.")
    if len(active_sources) <= 3:
        warnings.append("Low source diversity: only a few sources produced events.")
    if chrome_count <= 10:
        warnings.append("Chrome evidence volume is low; browser activity may be under-captured.")
    return warnings

