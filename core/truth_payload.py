"""Versioned JSON payload for sessions + events (Gittan / extension spine)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from core.cli import package_version

TRUTH_PAYLOAD_VERSION = "1"

_URL_SCHEME_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _redact_chrome_detail_for_json(detail: str) -> str:
    """Strip raw URLs from Chrome event detail for machine-readable exports."""
    text = str(detail or "").strip()
    if " — " in text:
        head = text.split(" — ", 1)[0].strip()
        return (head or "Chrome visit")[:240]
    if _URL_SCHEME_RE.fullmatch(text):
        return "Chrome visit"
    redacted = _URL_SCHEME_RE.sub("[url]", text).strip()
    return (redacted or "Chrome visit")[:240]


def _serialize_event(
    event: Dict[str, Any],
    local_ts: datetime | None = None,
    *,
    redact_chrome_raw_json: bool = False,
) -> Dict[str, Any]:
    ts = event.get("timestamp")
    if not isinstance(ts, datetime):
        raise TypeError("event['timestamp'] must be datetime")
    detail_raw = str(event.get("detail", "") or "")
    if redact_chrome_raw_json and str(event.get("source", "")) == "Chrome":
        detail_out = _redact_chrome_detail_for_json(detail_raw)
    else:
        detail_out = detail_raw
    out: Dict[str, Any] = {
        "source": event.get("source", ""),
        "timestamp": _iso_utc(ts),
        "detail": detail_out,
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
    redact_chrome_raw_json: bool = False,
    attendance: str | None = None,
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
    if attendance is None:
        attendance = session_events[0].get("attendance") if session_events and "attendance" in session_events[0] else None
    if attendance is None:
        from core.domain import classify_attendance

        attendance = classify_attendance(session_events)

    events_out = []
    for ev in session_events:
        lt = ev.get("local_ts")
        if isinstance(lt, datetime):
            events_out.append(_serialize_event(ev, local_ts=lt, redact_chrome_raw_json=redact_chrome_raw_json))
        else:
            events_out.append(_serialize_event(ev, redact_chrome_raw_json=redact_chrome_raw_json))
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
        "attendance": attendance,
        "events": events_out,
    }


def build_truth_payload(
    *,
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    included_events: List[Dict[str, Any]],
    collector_status: Dict[str, Dict[str, Any]],
    screen_time_days: Dict[str, float] | None,
    presence_estimated: Any | None = None,
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
    worklog_paths: list[str] | None = None,
    session_duration_hours_fn,
    chrome_raw: bool = False,
) -> Dict[str, Any]:
    """Build a JSON-serializable dict aligned with existing session rules."""
    days_out: Dict[str, Any] = {}
    for day in sorted(overall_days.keys()):
        payload = overall_days[day]
        sessions_raw: List[Tuple[datetime, datetime, List[Dict[str, Any]]]] = payload["sessions"]
        sessions_out = []
        redact = bool(chrome_raw)
        for idx, s_tuple in enumerate(sessions_raw, start=1):
            start_ts, end_ts, session_events = s_tuple[:3]
            attendance = s_tuple[3] if len(s_tuple) > 3 else None
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
                    redact_chrome_raw_json=redact,
                    attendance=attendance,
                )
            )
        entries = payload.get("entries") or []
        events_flat = []
        for ev in entries:
            lt = ev.get("local_ts")
            if isinstance(lt, datetime):
                events_flat.append(_serialize_event(ev, local_ts=lt, redact_chrome_raw_json=redact))
            else:
                events_flat.append(_serialize_event(ev, redact_chrome_raw_json=redact))
        days_out[day] = {
            "hours_estimated": round(float(payload["hours"]), 6),
            "attended_hours": round(float(payload.get("attended_hours", 0.0)), 6),
            "mixed_hours": round(float(payload.get("mixed_hours", 0.0)), 6),
            "agent_hours": round(float(payload.get("agent_hours", 0.0)), 6),
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

    presence_block: Dict[str, Any] | None = None
    if presence_estimated is not None and getattr(presence_estimated, "available", False):
        presence_block = {
            "total_hours": round(float(presence_estimated.total_hours), 6),
            "hours_by_day": dict(sorted(presence_estimated.overall_days.items())),
            "projects_by_day": {
                project: dict(sorted(days.items()))
                for project, days in sorted(presence_estimated.project_days.items())
            },
            "label": "presence_estimated",
            "note": "Screen-Time-bounded estimate between evidenced events; not billable.",
        }

    paths_block: Dict[str, Any] = {
        "projects_config": config_path or "",
    }
    resolved_worklogs = list(worklog_paths or [])
    if source_strategy_effective == "per-project":
        paths_block["worklogs"] = resolved_worklogs
        paths_block["worklog"] = ""
    else:
        paths_block["worklog"] = worklog_path
        if len(resolved_worklogs) > 1:
            paths_block["worklogs"] = resolved_worklogs

    out: Dict[str, Any] = {
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
            **({"chrome_raw_json_detail_redacted": True} if chrome_raw else {}),
        },
        "source_roles": {
            "primary_source": primary_source,
            "mode": source_strategy_effective,
        },
        "paths": paths_block,
        "collector_status": collector_status,
        "screen_time_hours_by_day": screen_block,
        "totals": {
            "hours_estimated": round(sum(d["hours_estimated"] for d in days_out.values()), 6),
            "attended_hours": round(sum(d["attended_hours"] for d in days_out.values()), 6),
            "mixed_hours": round(sum(d["mixed_hours"] for d in days_out.values()), 6),
            "agent_hours": round(sum(d["agent_hours"] for d in days_out.values()), 6),
            "days_with_activity": len(days_out),
            "event_count": len(included_events),
        },
        "projects": project_totals,
        "days": days_out,
    }
    if presence_block is not None:
        out["presence_estimated_hours"] = presence_block
    return out
