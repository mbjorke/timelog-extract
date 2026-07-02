"""Shared helpers for report/status Typer commands (keeps cli_report_status.py smaller)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Optional, cast

from core.cli_options import TimelogRunOptions
from core.cli_prompts import prompt_for_timeframe


def shadow_log_status_line(status: Optional[Mapping[str, object]]) -> Optional[str]:
    """One-line summary of an opt-in shadow-log capture, or None when inactive."""
    if not status:
        return None
    if status.get("error"):
        return f"Shadow log: capture failed ({status['error']})."
    return (
        f"Shadow log: +{status.get('appended', 0)} new evidence records "
        f"({status.get('skipped', 0)} already stored) → {status.get('base_dir', '')}"
    )


def capture_shadow_log_line(
    shadow_log: object, events: object, config_path: object = None
) -> Optional[str]:
    """Run the opt-in capture and return its one-line summary (or None when off).

    ``config_path`` lets the "auto" flag default defer to the persistent
    ``"shadow_log"`` setting in the projects config (GH-274).
    """
    from core.evidence_store import capture_if_enabled

    return shadow_log_status_line(
        capture_if_enabled(shadow_log, events, config_path=config_path)
    )


def shadow_replay_line(restored: object) -> Optional[str]:
    """One-line note when stored evidence was replayed for a closed window."""
    try:
        count = int(restored or 0)
    except (TypeError, ValueError):
        return None
    if count <= 0:
        return None
    return f"Shadow-log replay: restored {count} event(s) from local evidence (upstream source rotated)."


def timeframe_from_prompt(picked: Mapping[str, object]) -> tuple[
    Optional[str], Optional[str], bool, bool, bool, bool, bool, bool
]:
    """Map `prompt_for_timeframe()` output into the normalized timeframe tuple."""
    return (
        cast(Optional[str], picked.get("date_from")),
        cast(Optional[str], picked.get("date_to")),
        bool(picked.get("today", False)),
        bool(picked.get("yesterday", False)),
        bool(picked.get("last_3_days", False)),
        bool(picked.get("last_week", False)),
        bool(picked.get("last_14_days", False)),
        bool(picked.get("last_month", False)),
    )


def resolve_timeframe_args(
    *,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    today: bool,
    yesterday: bool,
    last_3_days: bool,
    last_week: bool,
    last_14_days: bool,
    last_month: bool,
) -> tuple[Optional[str], Optional[str], bool, bool, bool, bool, bool, bool]:
    """Normalize timeframe flags for `report`/`search`; prompt when omitted."""
    if not (
        today
        or yesterday
        or last_3_days
        or last_week
        or last_14_days
        or last_month
        or date_from
        or date_to
    ):
        picked = prompt_for_timeframe()
        return timeframe_from_prompt(picked)
    return (
        date_from.strftime("%Y-%m-%d") if date_from else None,
        date_to.strftime("%Y-%m-%d") if date_to else None,
        today,
        yesterday,
        last_3_days,
        last_week,
        last_14_days,
        last_month,
    )


def build_report_options(
    *,
    timeframe: tuple[Optional[str], Optional[str], bool, bool, bool, bool, bool, bool],
    option_fields: dict[str, object],
    overrides: Optional[dict[str, object]] = None,
) -> TimelogRunOptions:
    """Build `TimelogRunOptions` from normalized timeframe fields + command-specific fields.

    `overrides` is applied last so callers can enforce command-specific invariants
    (for example `search` forcing `all_events=True`).
    """
    df_s, dt_s, today, yesterday, last_3_days, last_week, last_14_days, last_month = timeframe
    payload: dict[str, object] = {
        "date_from": df_s,
        "date_to": dt_s,
        "today": today,
        "yesterday": yesterday,
        "last_3_days": last_3_days,
        "last_week": last_week,
        "last_14_days": last_14_days,
        "last_month": last_month,
    }
    payload.update(option_fields)
    if overrides:
        payload.update(overrides)
    return TimelogRunOptions(**payload)


def run_status_timelog_report(
    console: object,
    *,
    projects_config: str,
    date_from: str,
    date_to: str,
    options: TimelogRunOptions,
    title_date: str,
) -> object:
    """Collect report payload for `gittan status`, with a TTY spinner when interactive."""
    from core.anchor_nudge import should_prompt
    from core.report_service import run_timelog_report
    from outputs.terminal_theme import CLR_DIM

    if should_prompt():
        with console.status(  # type: ignore[attr-defined]
            f"[{CLR_DIM}]Collecting activity for status ({title_date})…[/{CLR_DIM}]",
            spinner="dots",
        ):
            return run_timelog_report(projects_config, date_from, date_to, options)
    return run_timelog_report(projects_config, date_from, date_to, options)


def print_status_anchor_nudge(console: object, report: object, *, anchor_nudge: bool) -> None:
    """Scan anchors under spinner when needed; prompt or warn on a TTY."""
    if not anchor_nudge:
        return
    from core.anchor_nudge import (
        maybe_run_interactive_anchor_mapping,
        should_prompt,
        status_anchor_line,
    )
    from core.report_postamble import scan_unmapped_anchors_with_status
    from outputs.terminal_theme import CLR_VALUE_ORANGE, STYLE_MUTED

    config_path = str(getattr(getattr(report, "args", None), "projects_config", "") or "")
    console.print()  # type: ignore[attr-defined]
    unmapped_anchors = scan_unmapped_anchors_with_status(console, report, ignore_quiet=True)
    if unmapped_anchors and should_prompt():
        maybe_run_interactive_anchor_mapping(
            console,
            report,
            projects_config=config_path,
            anchors=unmapped_anchors,
        )
        return
    if not unmapped_anchors:
        return
    warn_line = status_anchor_line(unmapped_anchors)
    if not warn_line:
        return
    console.print(f"[{CLR_VALUE_ORANGE}]{warn_line}[/{CLR_VALUE_ORANGE}]")  # type: ignore[attr-defined]
    console.print(  # type: ignore[attr-defined]
        f"[{STYLE_MUTED}]Run `gittan map` to review and apply project mappings.[/{STYLE_MUTED}]"
    )
