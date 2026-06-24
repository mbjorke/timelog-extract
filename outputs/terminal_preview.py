"""Session preview selection for terminal reports (high-signal first, log noise hidden)."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from rich.text import Text

from core.events import event_anchors

_CURSOR_PREVIEW_NOISE_MARKERS = (
    ".git —",
    "hooks.json —",
    "settings.json —",
    "settings.local.json —",
    "pygls.protocol",
    "failed to handle request",
    "> git --git-dir",
    "revived process, old id",
    "project config path",
    "claude project config path",
    "claude project local config path",
    ".envs —",
    "running deep link",
    "[model][openrepository]",
    "bootstrapping repository index",
    "skipping acquiring lock",
    "cursor_agent_exec",
)


def event_detail_parts(event: dict) -> tuple[str, str]:
    """Return (label_prefix, detail) for styled terminal rows."""
    detail = str(event.get("detail") or "")
    label = str(event_anchors(event).get("label") or "").strip()
    if not label:
        return "", detail
    if detail.lower().strip() == label:
        return "", detail
    if label in detail.lower():
        return "", detail
    return label, detail if detail else label


def format_event_detail(event: dict) -> str:
    """Prefer session title over IDE log tails; composer rows show title only."""
    label, detail = event_detail_parts(event)
    if not label:
        return detail
    return f"{label}: {detail}" if detail else label


def assemble_timeline_event_detail(
    event: dict,
    *,
    label_style: str,
    detail_style: str,
) -> Text:
    label, detail = event_detail_parts(event)
    if label:
        return Text.assemble((f"{label}: ", label_style), (detail, detail_style))
    return Text(format_event_detail(event), style=detail_style)


def assemble_timeline_event_line(
    event: dict,
    *,
    source_label: str,
    source_style: str,
    time_style: str,
    project_style: str,
    label_style: str,
    detail_style: str,
) -> Text:
    return Text.assemble(
        (f"{event['local_ts'].strftime('%H:%M')} ", time_style),
        (f"{source_label} ", source_style),
        (f"{event['project']} ", project_style),
        assemble_timeline_event_detail(
            event, label_style=label_style, detail_style=detail_style
        ),
    )


def _is_high_signal_preview_event(event: Dict[str, Any]) -> bool:
    """Session titles, worklog, Lovable UUIDs, GitHub — always show in preview."""
    if event_anchors(event).get("label"):
        return True
    source = str(event.get("source") or "")
    detail = str(event.get("detail") or "").lower()
    if source == "Lovable (desktop)" and "storage signal" in detail:
        return True
    if "worklog" in source.lower() or source == "TIMELOG.md":
        return True
    if source == "GitHub":
        return True
    if source == "Chrome" and "file not found" not in detail:
        return True
    return False


def _is_low_signal_preview_event(event: Dict[str, Any]) -> bool:
    """IDE log churn and dead Chrome rows — hidden only with --compact."""
    if _is_high_signal_preview_event(event):
        return False
    source = str(event.get("source") or "")
    detail = str(event.get("detail") or "").lower()
    if source == "Chrome" and "file not found" in detail:
        return True
    if source != "Cursor":
        return False
    # Composer sessions carry label; output.log lines do not.
    if not event_anchors(event).get("label"):
        return True
    return any(marker in detail for marker in _CURSOR_PREVIEW_NOISE_MARKERS)


def pick_session_preview_events(
    session_events: Sequence[Dict[str, Any]],
    source_order: Sequence[str],
    max_lines: int | None = None,
) -> List[Dict[str, Any]]:
    """Show every evidence row except Cursor/Chrome log noise (no arbitrary cap)."""
    del source_order  # kept for callers; ordering is chronological only
    ordered = sorted(session_events, key=lambda e: e["local_ts"])
    picked = [e for e in ordered if not _is_low_signal_preview_event(e)]
    if max_lines is not None and len(picked) > max_lines:
        return picked[:max_lines]
    return picked


def session_preview_omitted_summary(
    session_events: Sequence[Dict[str, Any]],
    display_events: Sequence[Dict[str, Any]],
) -> str | None:
    """Human-readable footer when preview hides rows (noise vs other evidence)."""
    if len(display_events) >= len(session_events):
        return None
    shown = {id(e) for e in display_events}
    hidden = [e for e in session_events if id(e) not in shown]
    noise_hidden = sum(1 for e in hidden if _is_low_signal_preview_event(e))
    other_hidden = len(hidden) - noise_hidden
    if not noise_hidden:
        return None
    noun = "line" if noise_hidden == 1 else "lines"
    return f"… {noise_hidden} IDE log {noun} hidden — omit --compact for full detail"
