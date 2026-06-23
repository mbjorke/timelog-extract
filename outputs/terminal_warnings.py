"""Report footer warnings (plausibility, cache-evidence codecs)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from core.cache_evidence_health import codec_blocked_sources, codec_warning_lines
from core.evidence_diagnostics import screen_time_incomplete_warnings
from core.sanity_bounds import plausibility_warnings
from outputs.terminal_theme import CLR_VALUE_ORANGE, WARN_ICON


def print_report_warnings(
    console: Any,
    *,
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    observed_hours: float,
    screen_time_hours: Optional[float],
    screen_time_days: Optional[Dict[str, float]] = None,
    session_duration_hours_fn: Any,
    args: Any,
) -> None:
    warnings = plausibility_warnings(
        overall_days=overall_days,
        project_reports=project_reports,
        observed_hours=observed_hours,
        screen_time_hours=screen_time_hours,
        session_duration_hours_fn=session_duration_hours_fn,
        min_session_minutes=getattr(args, "min_session", 15),
        min_session_passive_minutes=getattr(args, "min_session_passive", 5),
    )
    warnings.extend(screen_time_incomplete_warnings(screen_time_days, overall_days))
    for warning in warnings:
        console.print(f"{WARN_ICON} [{CLR_VALUE_ORANGE}]{warning}[/{CLR_VALUE_ORANGE}]")
    for warning in codec_warning_lines(codec_blocked_sources(Path.home())):
        console.print(f"{WARN_ICON} [{CLR_VALUE_ORANGE}]{warning}[/{CLR_VALUE_ORANGE}]")
