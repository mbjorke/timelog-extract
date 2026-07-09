"""GH-332 Slice 2: extend evidenced sessions into adjacent presence (capped).

Presence **brackets** evidence — it never invents project attribution.
Bracketed minutes inherit the session's existing project mix via the normal
allocation path after wall-clock is extended.

Opt-in: ``--presence-bracket on`` (requires ``--timely-memory-source on``).
Default edge cap: ``DEFAULT_EDGE_CAP_MINUTES`` (10). Billable gating for
bracketed minutes remains subject to GH-327; until then they follow the same
approval path as other observed time (nothing is billable until approved).
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Sequence

from core.presence_edge_gaps import (
    DEFAULT_EDGE_CAP_MINUTES,
    DEFAULT_PRESENCE_BRIDGE_SECONDS,
    _clip_edge_interval,
    _covering_presence,
    _merge_presence_spans,
    _session_bounds,
)


@dataclass(frozen=True)
class BracketedSession:
    day: str
    session_index: int
    evidence_start: datetime
    evidence_end: datetime
    bracketed_start: datetime
    bracketed_end: datetime
    lead_seconds: float
    trail_seconds: float

    @property
    def bracketed_seconds(self) -> float:
        return self.lead_seconds + self.trail_seconds


@dataclass
class BracketingResult:
    """Result of applying capped presence brackets to overall_days."""

    applied: bool = False
    reason: str = ""
    edge_cap_minutes: int = DEFAULT_EDGE_CAP_MINUTES
    overall_days: Dict[str, Any] | None = None
    sessions: List[BracketedSession] | None = None
    total_bracketed_hours: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        if not self.applied:
            return {
                "applied": False,
                "reason": self.reason or "bracketing not applied",
                "label": "presence_bracketing",
                "note": (
                    "GH-332 Slice 2: capped presence brackets on evidenced sessions. "
                    "Off unless --presence-bracket on with Timely Memory spans."
                ),
            }
        return {
            "applied": True,
            "edge_cap_minutes": self.edge_cap_minutes,
            "total_bracketed_hours": round(self.total_bracketed_hours, 6),
            "session_count_bracketed": sum(
                1 for s in (self.sessions or []) if s.bracketed_seconds > 0
            ),
            "sessions": [
                {
                    "day": s.day,
                    "session_index": s.session_index,
                    "evidence_start": s.evidence_start.isoformat(),
                    "evidence_end": s.evidence_end.isoformat(),
                    "bracketed_start": s.bracketed_start.isoformat(),
                    "bracketed_end": s.bracketed_end.isoformat(),
                    "lead_hours": round(s.lead_seconds / 3600.0, 6),
                    "trail_hours": round(s.trail_seconds / 3600.0, 6),
                    "bracketed_hours": round(s.bracketed_seconds / 3600.0, 6),
                }
                for s in (self.sessions or [])
                if s.bracketed_seconds > 0
            ],
            "label": "presence_bracketing",
            "note": (
                "Session wall-clock extended into adjacent Timely Memory presence, "
                "capped per edge. Project identity still comes from evidence events "
                "only (GH-332 Slice 2)."
            ),
        }


def _capped_lead_trail(
    start_ts: datetime,
    end_ts: datetime,
    *,
    prev_end: datetime | None,
    next_start: datetime | None,
    merged_presence: Sequence[tuple[datetime, datetime]],
    cap: timedelta,
) -> tuple[float, float]:
    """Return (lead_seconds, trail_seconds) clipped to neighbors and edge cap."""
    lead_seconds = 0.0
    trail_seconds = 0.0

    covering_start = _covering_presence(start_ts, merged_presence)
    if covering_start is not None:
        p_start, p_end = covering_start
        if prev_end is not None and p_start <= prev_end < p_end:
            clipped_lead = None
        else:
            clipped_lead = _clip_edge_interval(
                p_start, start_ts, floor=prev_end, ceiling=start_ts
            )
        if clipped_lead is not None:
            capped = _clip_edge_interval(
                start_ts - cap, start_ts, floor=clipped_lead[0], ceiling=start_ts
            )
            if capped is not None:
                lead_seconds = (capped[1] - capped[0]).total_seconds()

    covering_end = _covering_presence(end_ts, merged_presence)
    if covering_end is not None:
        _p_start, p_end = covering_end
        clipped = _clip_edge_interval(end_ts, p_end, floor=end_ts, ceiling=next_start)
        if clipped is not None:
            capped = _clip_edge_interval(
                end_ts, end_ts + cap, floor=end_ts, ceiling=clipped[1]
            )
            if capped is not None:
                trail_seconds = (capped[1] - capped[0]).total_seconds()

    return lead_seconds, trail_seconds


def presence_bracketing_enabled(args: Any) -> bool:
    mode = str(getattr(args, "presence_bracket", "off") or "off").strip().lower()
    return mode in {"on", "true", "1", "yes"}


def presence_bracket_cap_minutes(args: Any) -> int:
    raw = getattr(args, "presence_bracket_cap_minutes", DEFAULT_EDGE_CAP_MINUTES)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_EDGE_CAP_MINUTES


def apply_presence_bracketing(
    overall_days: Dict[str, Any],
    presence_spans: Sequence[tuple[datetime, datetime]] | None,
    *,
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
    edge_cap_minutes: int = DEFAULT_EDGE_CAP_MINUTES,
    bridge_seconds: int = DEFAULT_PRESENCE_BRIDGE_SECONDS,
) -> BracketingResult:
    """Return a deep-copied overall_days with capped presence brackets applied.

    Does not invent sessions: only stretches existing evidenced session edges.
    Zero-duration / floor-only sessions still get wall-clock from the extension.
    """
    if not presence_spans:
        return BracketingResult(
            applied=False,
            reason="no span-level presence (enable --timely-memory-source on)",
            edge_cap_minutes=edge_cap_minutes,
        )

    merged = _merge_presence_spans(presence_spans, bridge_seconds=bridge_seconds)
    sessions = _session_bounds(overall_days)
    if not sessions:
        return BracketingResult(
            applied=False,
            reason="no evidenced sessions",
            edge_cap_minutes=edge_cap_minutes,
        )

    cap = timedelta(minutes=max(0, edge_cap_minutes))
    # Map (day, session_index) -> (lead, trail) for capped extensions.
    extensions: dict[tuple[str, int], tuple[float, float]] = {}
    bracketed_meta: list[BracketedSession] = []
    for i, (day, idx, start_ts, end_ts) in enumerate(sessions):
        prev_end = sessions[i - 1][3] if i > 0 else None
        next_start = sessions[i + 1][2] if i + 1 < len(sessions) else None
        lead_s, trail_s = _capped_lead_trail(
            start_ts,
            end_ts,
            prev_end=prev_end,
            next_start=next_start,
            merged_presence=merged,
            cap=cap,
        )
        extensions[(day, idx)] = (lead_s, trail_s)
        new_start = start_ts - timedelta(seconds=lead_s)
        new_end = end_ts + timedelta(seconds=trail_s)
        bracketed_meta.append(
            BracketedSession(
                day=day,
                session_index=idx,
                evidence_start=start_ts,
                evidence_end=end_ts,
                bracketed_start=new_start,
                bracketed_end=new_end,
                lead_seconds=lead_s,
                trail_seconds=trail_s,
            )
        )

    if not any(lead + trail > 0 for lead, trail in extensions.values()):
        return BracketingResult(
            applied=False,
            reason="no capped edge presence adjacent to sessions",
            edge_cap_minutes=edge_cap_minutes,
            sessions=bracketed_meta,
        )

    out = deepcopy(overall_days)
    total_bracketed = 0.0
    for day in sorted(out.keys()):
        payload = out[day]
        raw_sessions = list(payload.get("sessions") or [])
        new_sessions = []
        day_bracketed = 0.0
        day_hours = 0.0
        attended_h = 0.0
        mixed_h = 0.0
        agent_h = 0.0
        for idx, s_tuple in enumerate(raw_sessions, start=1):
            start_ts, end_ts, events = s_tuple[0], s_tuple[1], s_tuple[2]
            attendance = s_tuple[3] if len(s_tuple) > 3 else None
            lead_s, trail_s = extensions.get((day, idx), (0.0, 0.0))
            new_start = start_ts - timedelta(seconds=lead_s)
            new_end = end_ts + timedelta(seconds=trail_s)
            hours = session_duration_hours_fn(
                events,
                new_start,
                new_end,
                min_session_minutes,
                min_session_passive_minutes,
            )
            evidence_hours = session_duration_hours_fn(
                events,
                start_ts,
                end_ts,
                min_session_minutes,
                min_session_passive_minutes,
            )
            bracketed = max(0.0, hours - evidence_hours)
            day_bracketed += bracketed
            day_hours += hours
            if attendance == "attended":
                attended_h += hours
            elif attendance == "mixed":
                mixed_h += hours
            elif attendance == "agent":
                agent_h += hours
            if attendance is None:
                new_sessions.append((new_start, new_end, events))
            else:
                new_sessions.append((new_start, new_end, events, attendance))

        payload["sessions"] = new_sessions
        payload["hours"] = day_hours
        payload["bracketed_hours"] = day_bracketed
        payload["evidenced_hours"] = max(0.0, day_hours - day_bracketed)
        if attended_h or mixed_h or agent_h:
            payload["attended_hours"] = attended_h
            payload["mixed_hours"] = mixed_h
            payload["agent_hours"] = agent_h
        total_bracketed += day_bracketed

    return BracketingResult(
        applied=True,
        edge_cap_minutes=edge_cap_minutes,
        overall_days=out,
        sessions=bracketed_meta,
        total_bracketed_hours=total_bracketed,
    )
