"""Helpers for evidence coverage diagnostics in CLI flows."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def build_evidence_snapshot(report: Any) -> Dict[str, Any]:
    source_counts = Counter(str(event.get("source") or "") for event in report.included_events)
    source_counts.pop("", None)
    observed_hours = float(sum(float(day.get("hours", 0.0) or 0.0) for day in report.overall_days.values()))
    screen_values = [float(v or 0.0) for v in (report.screen_time_days or {}).values()]
    # Some runtime paths expose Screen Time as seconds/day; normalize to hours.
    screen_time_hours = float(sum(v / 3600.0 for v in screen_values)) if any(v > 24.0 for v in screen_values) else float(sum(screen_values))
    delta_hours = screen_time_hours - observed_hours
    return {
        "observed_hours": observed_hours,
        "screen_time_hours": screen_time_hours,
        "delta_hours": delta_hours,
        "source_counts": dict(source_counts),
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

