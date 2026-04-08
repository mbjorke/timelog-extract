"""Date-range and reporting aggregation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta


def get_date_range(date_from, date_to, local_tz):
    now_local = datetime.now(local_tz)
    if date_from:
        start_local = datetime.strptime(date_from, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=local_tz
        )
    else:
        start_local = (now_local - timedelta(days=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    if date_to:
        end_local = datetime.strptime(date_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=0, tzinfo=local_tz
        )
    else:
        end_local = now_local
    return start_local, end_local


def group_by_day(events, local_tz, exclude_keywords=None):
    excl = [k.lower() for k in (exclude_keywords or [])]
    days = {}
    for event in events:
        detail_lower = event.get("detail", "").lower()
        if excl and any(kw in detail_lower for kw in excl):
            continue
        local_ts = event["timestamp"].astimezone(local_tz)
        day = local_ts.date().isoformat()
        days.setdefault(day, []).append({**event, "local_ts": local_ts})
    return days


def estimate_hours_by_day(
    days,
    gap_minutes,
    min_session_minutes,
    min_session_passive_minutes,
    compute_sessions_fn,
    session_duration_hours_fn,
):
    per_day = {}
    for day, entries in days.items():
        sessions = compute_sessions_fn(entries, gap_minutes=gap_minutes)
        total_h = 0.0
        for start, end, events in sessions:
            raw = session_duration_hours_fn(
                events, start, end, min_session_minutes, min_session_passive_minutes
            )
            total_h += raw
        per_day[day] = {"entries": entries, "sessions": sessions, "hours": total_h}
    return per_day
