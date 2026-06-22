"""Shared date-window helpers for CLI commands."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from core.cli_prompts import prompt_for_timeframe

# Conservative lower bound for ``--history`` all-log scans; collectors only return
# events that still exist in their backing stores.
ALL_AVAILABLE_LOGS_FROM = date(2020, 1, 1)


def as_iso_date(value: Optional[datetime | str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)


def resolve_date_window(
    *,
    date_from: Optional[datetime | str],
    date_to: Optional[datetime | str],
    today: bool = False,
    yesterday: bool = False,
    last_3_days: bool = False,
    last_week: bool = False,
    last_14_days: bool = False,
    last_month: bool = False,
    prompt_if_missing: bool = False,
    fallback_recent_days: Optional[int] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Normalize explicit dates + relative flags into an ISO date window."""
    from_s = as_iso_date(date_from)
    to_s = as_iso_date(date_to)
    if from_s or to_s:
        return from_s, to_s
    if today or yesterday or last_3_days or last_week or last_14_days or last_month:
        end_d = date.today()
        if today:
            return end_d.isoformat(), end_d.isoformat()
        if yesterday:
            yest = (end_d - timedelta(days=1)).isoformat()
            return yest, yest
        if last_3_days:
            return (end_d - timedelta(days=2)).isoformat(), end_d.isoformat()
        if last_week:
            return (end_d - timedelta(days=6)).isoformat(), end_d.isoformat()
        if last_14_days:
            return (end_d - timedelta(days=13)).isoformat(), end_d.isoformat()
        return (end_d - timedelta(days=29)).isoformat(), end_d.isoformat()
    if prompt_if_missing:
        picked = prompt_for_timeframe()
        return str(picked.get("date_from") or "") or None, str(picked.get("date_to") or "") or None
    if fallback_recent_days and int(fallback_recent_days) > 0:
        end_d = date.today()
        start_d = end_d - timedelta(days=int(fallback_recent_days) - 1)
        return start_d.isoformat(), end_d.isoformat()
    return None, None


def has_explicit_date_window(
    *,
    date_from: Optional[datetime | str],
    date_to: Optional[datetime | str],
    today: bool = False,
    yesterday: bool = False,
    last_3_days: bool = False,
    last_week: bool = False,
    last_14_days: bool = False,
    last_month: bool = False,
) -> bool:
    """True when the caller set an explicit period (not ``--history`` all-logs mode)."""
    if as_iso_date(date_from) or as_iso_date(date_to):
        return True
    return bool(today or yesterday or last_3_days or last_week or last_14_days or last_month)


def resolve_all_available_window(*, now: Optional[date] = None) -> tuple[str, str]:
    """ISO window for scanning all logs Gittan can still read."""
    end_d = now or date.today()
    return ALL_AVAILABLE_LOGS_FROM.isoformat(), end_d.isoformat()
