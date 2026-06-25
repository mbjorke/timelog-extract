"""Shared cache-evidence health checks (doctor, evidence-check, report)."""

from __future__ import annotations

from pathlib import Path
from typing import List


def codec_missing_reason(reason: str) -> bool:
    """True when a cache status reason indicates a missing decode codec."""
    low = (reason or "").lower()
    return "missing" in low and any(word in low for word in ("codec", "zstandard", "brotli"))


def codec_blocked_sources(home: Path) -> List[tuple[str, str]]:
    """Sources that would silently under-count when a cache codec is missing."""
    from collectors.claude_desktop_events import claude_events_cache_status
    from collectors.lovable_cache import lovable_cache_status, lovable_desktop_has_cache_signals

    blocked: list[tuple[str, str]] = []
    events_ok, events_reason = claude_events_cache_status(home)
    if not events_ok and codec_missing_reason(events_reason):
        blocked.append(("Claude Desktop (Code)", events_reason))
    if lovable_desktop_has_cache_signals(home):
        cache_ok, cache_reason = lovable_cache_status(home)
        if not cache_ok and codec_missing_reason(cache_reason):
            blocked.append(("Lovable Desktop", cache_reason))
    return blocked


def codec_warning_lines(blocked: List[tuple[str, str]]) -> List[str]:
    if not blocked:
        return []
    from core.chromium_cache import CODEC_REINSTALL_HINT

    names = ", ".join(source for source, _reason in blocked)
    return [
        f"Cache codec missing for: {names}. Reinstall: {CODEC_REINSTALL_HINT}"
    ]
