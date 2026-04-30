"""Soft, non-blocking nudges shown in report/status surfaces."""

from __future__ import annotations

from urllib.parse import urlparse

from core.calibration.screen_time_gap import analyze_screen_time_gaps

# MVP default: nudge when unexplained gap exceeds one focused session.
UNEXPLAINED_GAP_NUDGE_THRESHOLD_HOURS = 1.5
UNCATEGORIZED_NUDGE_THRESHOLD_HOURS = 2.0
UNCATEGORIZED_NUDGE_THRESHOLD_RATIO = 0.35
UNCATEGORIZED_NOISE_SUPPRESSION_RATIO = 0.8
_TRIAGE_NOISE_DOMAINS = {"cursor.com", "cursor.sh"}
_TRIAGE_NOISE_TITLE_MARKERS = (
    "canvas sdk mirror failed",
    "skills-cursor",
    "cursor sdk",
    "mcp tool schema",
    "cursor extension host",
    "cursor diagnostics",
)


def uncategorized_hours_by_day(report) -> dict[str, float]:
    uncategorized = report.project_reports.get("Uncategorized", {}) if hasattr(report, "project_reports") else {}
    return {
        str(day): float((day_data or {}).get("hours", 0.0) or 0.0)
        for day, day_data in uncategorized.items()
        if float((day_data or {}).get("hours", 0.0) or 0.0) > 0.0
    }


def _total_hours_by_day(report) -> dict[str, float]:
    overall = report.overall_days if hasattr(report, "overall_days") else {}
    return {
        str(day): float((day_data or {}).get("hours", 0.0) or 0.0)
        for day, day_data in overall.items()
    }


def _noise_domain_from_detail(detail: str) -> str:
    text = str(detail or "")
    for token in text.split():
        if not token.startswith("http://") and not token.startswith("https://"):
            continue
        try:
            host = urlparse(token).netloc.lower().strip()
        except Exception:
            continue
        if host.startswith("www."):
            host = host[4:]
        return host
    return ""


def _uncategorized_noise_ratio_for_day(report, *, day: str) -> float:
    events = list(getattr(report, "included_events", []) or [])
    if not events:
        return 0.0
    total = 0
    noise = 0
    for event in events:
        event_day = str(event.get("day") or event.get("date") or "")[:10]
        if event_day != day:
            continue
        if str(event.get("project") or "").strip() != "Uncategorized":
            continue
        total += 1
        detail = str(event.get("detail") or "")
        domain = _noise_domain_from_detail(detail)
        if domain in _TRIAGE_NOISE_DOMAINS:
            noise += 1
            continue
        lowered = detail.lower()
        if any(marker in lowered for marker in _TRIAGE_NOISE_TITLE_MARKERS):
            noise += 1
    if total == 0:
        return 0.0
    return float(noise) / float(total)


def uncategorized_nudge_candidate(report, *, threshold_hours: float, threshold_ratio: float) -> dict[str, float | str] | None:
    uncategorized_by_day = uncategorized_hours_by_day(report)
    if not uncategorized_by_day:
        return None
    total_by_day = _total_hours_by_day(report)
    best: dict[str, float | str] | None = None
    for day, uncategorized_h in uncategorized_by_day.items():
        total_h = float(total_by_day.get(day, 0.0) or 0.0)
        ratio = (uncategorized_h / total_h) if total_h > 0 else 0.0
        if uncategorized_h < float(threshold_hours) or ratio < float(threshold_ratio):
            continue
        if _uncategorized_noise_ratio_for_day(report, day=day) >= float(UNCATEGORIZED_NOISE_SUPPRESSION_RATIO):
            continue
        if best is None or uncategorized_h > float(best.get("uncategorized_hours", 0.0)):
            best = {
                "day": day,
                "uncategorized_hours": uncategorized_h,
                "total_hours": total_h,
                "ratio": ratio,
            }
    return best


def build_unexplained_gap_nudge(report, *, threshold_hours: float = UNEXPLAINED_GAP_NUDGE_THRESHOLD_HOURS) -> str | None:
    required_attrs = ("screen_time_days", "overall_days", "project_reports")
    if not all(hasattr(report, attr) for attr in required_attrs):
        return None
    payload = analyze_screen_time_gaps(report)
    max_unexplained = 0.0
    worst_day = ""
    for row in payload.get("days", []):
        unexplained = float(row.get("unexplained_screen_time_hours", 0.0) or 0.0)
        if unexplained > max_unexplained:
            max_unexplained = unexplained
            worst_day = str(row.get("day") or "")
    if max_unexplained < float(threshold_hours):
        max_unexplained = 0.0
        worst_day = ""
    uncategorized = uncategorized_nudge_candidate(
        report,
        threshold_hours=UNCATEGORIZED_NUDGE_THRESHOLD_HOURS,
        threshold_ratio=UNCATEGORIZED_NUDGE_THRESHOLD_RATIO,
    )
    if max_unexplained >= float(threshold_hours):
        return (
            f"Nudge: {max_unexplained:.1f}h unexplained screen-time on {worst_day}. "
            "Run `gittan triage-guided` to review evidence."
        )
    if uncategorized:
        day = str(uncategorized["day"])
        unc_h = float(uncategorized["uncategorized_hours"])
        ratio = float(uncategorized["ratio"])
        return (
            f"Nudge: {unc_h:.1f}h Uncategorized ({ratio:.0%}) on {day}. "
            "Run `gittan triage-guided` to review evidence."
        )
    return None
