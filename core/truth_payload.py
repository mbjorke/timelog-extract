"""Versioned JSON payload for sessions + events (Gittan / extension spine)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from core.cli import package_version

TRUTH_PAYLOAD_VERSION = "1"


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _serialize_event(event: Dict[str, Any], local_ts: datetime | None = None) -> Dict[str, Any]:
    ts = event.get("timestamp")
    if not isinstance(ts, datetime):
        raise TypeError("event['timestamp'] must be datetime")
    out: Dict[str, Any] = {
        "source": event.get("source", ""),
        "timestamp": _iso_utc(ts),
        "detail": event.get("detail", ""),
        "project": event.get("project", ""),
    }
    if local_ts is not None:
        out["local_time"] = local_ts.isoformat()
    return out


def _serialize_session(
    start_ts: datetime,
    end_ts: datetime,
    session_events: List[Dict[str, Any]],
    *,
    session_duration_hours_fn,
    min_session_minutes: int,
    min_session_passive_minutes: int,
    session_index: int,
    day: str,
) -> Dict[str, Any]:
    raw_hours = session_duration_hours_fn(
        session_events,
        start_ts,
        end_ts,
        min_session_minutes,
        min_session_passive_minutes,
    )
    projects = sorted({e.get("project", "") for e in session_events})
    sources = sorted({e.get("source", "") for e in session_events})
    events_out = []
    for ev in session_events:
        lt = ev.get("local_ts")
        if isinstance(lt, datetime):
            events_out.append(_serialize_event(ev, local_ts=lt))
        else:
            events_out.append(_serialize_event(ev))
    return {
        "id": f"{day}-{session_index}",
        "day": day,
        "start": _iso_utc(start_ts),
        "end": _iso_utc(end_ts),
        "start_local": start_ts.isoformat(),
        "end_local": end_ts.isoformat(),
        "hours_estimated": round(raw_hours, 6),
        "event_count": len(session_events),
        "projects": projects,
        "sources": sources,
        "events": events_out,
    }


def build_truth_payload(
    *,
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    included_events: List[Dict[str, Any]],
    collector_status: Dict[str, Dict[str, Any]],
    screen_time_days: Dict[str, float] | None,
    dt_from: datetime,
    dt_to: datetime,
    worklog_path: str,
    config_path: str | None,
    gap_minutes: int,
    min_session_minutes: int,
    min_session_passive_minutes: int,
    source_strategy_requested: str = "auto",
    source_strategy_effective: str = "balanced",
    primary_source: str = "balanced",
    session_duration_hours_fn,
) -> Dict[str, Any]:
    """Build a JSON-serializable dict aligned with existing session rules."""
    days_out: Dict[str, Any] = {}
    for day in sorted(overall_days.keys()):
        payload = overall_days[day]
        sessions_raw: List[Tuple[datetime, datetime, List[Dict[str, Any]]]] = payload["sessions"]
        sessions_out = []
        for idx, (start_ts, end_ts, session_events) in enumerate(sessions_raw, start=1):
            sessions_out.append(
                _serialize_session(
                    start_ts,
                    end_ts,
                    session_events,
                    session_duration_hours_fn=session_duration_hours_fn,
                    min_session_minutes=min_session_minutes,
                    min_session_passive_minutes=min_session_passive_minutes,
                    session_index=idx,
                    day=day,
                )
            )
        entries = payload.get("entries") or []
        events_flat = []
        for ev in entries:
            lt = ev.get("local_ts")
            if isinstance(lt, datetime):
                events_flat.append(_serialize_event(ev, local_ts=lt))
            else:
                events_flat.append(_serialize_event(ev))
        days_out[day] = {
            "hours_estimated": round(float(payload["hours"]), 6),
            "session_count": len(sessions_out),
            "sessions": sessions_out,
            "events": events_flat,
        }

    project_totals: Dict[str, float] = {}
    for pname, days in project_reports.items():
        project_totals[pname] = round(sum(d["hours"] for d in days.values()), 6)

    screen_block: Dict[str, Any] | None = None
    if screen_time_days is not None:
        screen_block = {
            k: round(v / 3600.0, 6) for k, v in sorted(screen_time_days.items())
        }

    return {
        "schema": "timelog_extract.truth_payload",
        "version": TRUTH_PAYLOAD_VERSION,
        "generator": {"package": "timelog-extract", "version": package_version()},
        "range": {
            "from": _iso_utc(dt_from),
            "to": _iso_utc(dt_to),
        },
        "settings": {
            "gap_minutes": gap_minutes,
            "min_session_minutes": min_session_minutes,
            "min_session_passive_minutes": min_session_passive_minutes,
            "source_strategy_requested": source_strategy_requested,
            "source_strategy_effective": source_strategy_effective,
        },
        "source_roles": {
            "primary_source": primary_source,
            "mode": source_strategy_effective,
        },
        "paths": {
            "worklog": worklog_path,
            "projects_config": config_path or "",
        },
        "collector_status": collector_status,
        "screen_time_hours_by_day": screen_block,
        "totals": {
            "hours_estimated": round(sum(d["hours_estimated"] for d in days_out.values()), 6),
            "days_with_activity": len(days_out),
            "event_count": len(included_events),
        },
        "projects": project_totals,
        "days": days_out,
    }
