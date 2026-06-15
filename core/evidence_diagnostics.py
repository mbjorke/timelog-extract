"""Evidence gap diagnostics for report vs Screen Time."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.cache_evidence_health import codec_blocked_sources, codec_warning_lines
from core.sources import AI_SOURCES

# Warn only when observed hours are below this fraction of Screen Time.
LOW_COVERAGE_RATIO = 0.5


def _screen_time_hours(screen_time_days: Dict[str, Any]) -> float:
    screen_values = [float(v or 0.0) for v in (screen_time_days or {}).values()]
    if not screen_values:
        return 0.0
    # Screen Time may be seconds/day (large integers) or hours/day (small floats).
    return float(sum((v / 3600.0) if v > 48.0 else v for v in screen_values))


def _has_mappable_unattributed(snapshot: Dict[str, Any]) -> bool:
    if snapshot.get("collected_but_excluded"):
        return True
    if int(snapshot.get("excluded_uncategorized_events", 0) or 0) > 0:
        return True
    return False


def build_evidence_warnings(
    snapshot: Dict[str, Any],
    *,
    home: Optional[Path] = None,
) -> List[str]:
    """Return user-facing warning lines for evidence gaps."""
    warnings: List[str] = []
    screen = float(snapshot.get("screen_time_hours", 0) or 0)
    observed = float(snapshot.get("observed_hours", 0) or 0)

    if screen > 0 and observed > 0 and observed <= screen:
        coverage = observed / screen
        if coverage < LOW_COVERAGE_RATIO and _has_mappable_unattributed(snapshot):
            pct = int(round(coverage * 100))
            warnings.append(
                f"Low project coverage ({pct}% of Screen Time). "
                "Run `gittan review` or `gittan map` for unmapped signal."
            )

    codec_blocked = list(snapshot.get("codec_blocked") or [])
    if not codec_blocked and home is not None:
        codec_blocked = codec_blocked_sources(home)
    warnings.extend(codec_warning_lines(codec_blocked))
    return warnings


def build_evidence_snapshot(
    report: Any,
    *,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build a compact evidence snapshot from a ReportPayload."""
    source_counts = Counter(str(event.get("source") or "") for event in report.included_events)
    source_counts.pop("", None)
    all_events = list(getattr(report, "all_events", None) or [])
    included = list(getattr(report, "included_events", None) or [])
    excluded_uncategorized = max(0, len(all_events) - len(included))
    collected_counts = Counter(str(event.get("source") or "") for event in all_events)
    collected_counts.pop("", None)
    collected_but_excluded = {
        source: count
        for source, count in collected_counts.items()
        if count > 0 and source_counts.get(source, 0) == 0
    }
    silent_ai_sources = sorted(
        source for source in AI_SOURCES if collected_counts.get(source, 0) == 0
    )
    observed_hours = float(
        sum(float(day.get("hours", 0.0) or 0.0) for day in (report.overall_days or {}).values())
    )
    screen_time_hours = _screen_time_hours(report.screen_time_days or {})
    delta_hours = screen_time_hours - observed_hours
    coverage_ratio = (observed_hours / screen_time_hours) if screen_time_hours > 0 else None
    codec_blocked = codec_blocked_sources(home) if home is not None else []

    return {
        "observed_hours": observed_hours,
        "screen_time_hours": screen_time_hours,
        "delta_hours": delta_hours,
        "coverage_ratio": round(coverage_ratio, 3) if coverage_ratio is not None else None,
        "source_counts": dict(source_counts),
        "excluded_uncategorized_events": excluded_uncategorized,
        "collected_but_excluded": collected_but_excluded,
        "silent_ai_sources": silent_ai_sources,
        "codec_blocked": codec_blocked,
    }
