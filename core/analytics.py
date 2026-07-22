"""Date-range and reporting aggregation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.sources import session_is_presence_signal_only


def get_date_range(date_from, date_to, local_tz):
    now_local = datetime.now(local_tz)
    if date_from:
        # fromisoformat is significantly faster than strptime.
        start_local = datetime.fromisoformat(date_from).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=local_tz
        )
    else:
        start_local = (now_local - timedelta(days=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    if date_to:
        # fromisoformat is significantly faster than strptime.
        end_local = datetime.fromisoformat(date_to).replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=local_tz
        )
    else:
        end_local = now_local
    return start_local, end_local


def group_by_day(events, local_tz, exclude_keywords=None):
    excl = [k.lower() for k in (exclude_keywords or [])]
    days = {}
    last_y = last_m = last_d = -1
    last_day_iso = ""

    for event in events:
        if excl:
            detail_lower = event.get("detail", "").lower()
            if any(kw in detail_lower for kw in excl):
                continue
        local_ts = event["timestamp"].astimezone(local_tz)

        # Performance optimization: cache local day ISO string formatting.
        # Avoids repeated expensive .date().isoformat() calls on datetime.
        y, m, d = local_ts.year, local_ts.month, local_ts.day
        if y == last_y and m == last_m and d == last_d:
            day = last_day_iso
        else:
            day = local_ts.date().isoformat()
            last_y, last_m, last_d = y, m, d
            last_day_iso = day

        copied = event.copy()
        copied["local_ts"] = local_ts
        days.setdefault(day, []).append(copied)
    return days


def estimate_hours_by_day(
    days,
    gap_minutes,
    min_session_minutes,
    min_session_passive_minutes,
    compute_sessions_fn,
    session_duration_hours_fn,
    classify_attendance_fn=None,
):
    per_day = {}
    for day, entries in days.items():
        sessions = compute_sessions_fn(entries, gap_minutes=gap_minutes)
        total_h = 0.0
        attended_h = 0.0
        mixed_h = 0.0
        agent_h = 0.0
        presence_h = 0.0
        session_data = []
        for start, end, events in sessions:
            raw = session_duration_hours_fn(
                events, start, end, min_session_minutes, min_session_passive_minutes
            )
            total_h += raw
            if session_is_presence_signal_only(events):
                presence_h += raw
            if classify_attendance_fn:
                attendance = classify_attendance_fn(events)
                session_data.append((start, end, events, attendance))
                if attendance == "attended":
                    attended_h += raw
                elif attendance == "mixed":
                    mixed_h += raw
                elif attendance == "agent":
                    agent_h += raw
            else:
                session_data.append((start, end, events))

        per_day[day] = {
            "entries": entries,
            "sessions": session_data,
            "hours": total_h,
            "attended_hours": attended_h,
            "mixed_hours": mixed_h,
            "agent_hours": agent_h,
            "presence_hours": presence_h,
        }
    return per_day
