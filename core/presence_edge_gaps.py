"""Measure adjacent presence at evidenced session edges (GH-332 Slice 1).

Diagnostics only: does **not** stretch sessions or change observed hours.
When Timely Memory (or another span-level presence source) shows continuous
presence immediately before the first event or after the last, report how many
minutes that edge gap covers. Slice 2 (bracketing) will optionally extend
spans using these measurements, with a cap + label.

Totals are **unique wall-clock** (merged edge intervals). Per-session lead/trail
may share an inter-session gap; summing session rows can exceed the unique total.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Sequence

# Bridge short stalls the same way Timely Memory folds samples into spans.
DEFAULT_PRESENCE_BRIDGE_SECONDS = 30
# Spec default for Slice 2; Slice 1 reports this as a "bracketable" preview.
DEFAULT_EDGE_CAP_MINUTES = 10


@dataclass(frozen=True)
class SessionEdgeGap:
    """Per-session lead/trail presence adjacent to an evidenced span."""

    day: str
    session_index: int
    session_start: datetime
    session_end: datetime
    lead_seconds: float
    trail_seconds: float
    presence_source: str

    @property
    def edge_seconds(self) -> float:
        return self.lead_seconds + self.trail_seconds


@dataclass
class EdgeGapReport:
    """Aggregate edge-gap diagnostic for a report window."""

    available: bool = False
    presence_source: str = ""
    sessions: List[SessionEdgeGap] = field(default_factory=list)
    reason: str = ""
    # Unique wall-clock outside evidenced sessions, adjacent to an edge.
    unique_lead_seconds: float = 0.0
    unique_trail_seconds: float = 0.0
    unique_edge_seconds: float = 0.0
    # Same unique intervals, each edge clipped to DEFAULT_EDGE_CAP_MINUTES.
    capped_edge_seconds: float = 0.0
    edge_cap_minutes: int = DEFAULT_EDGE_CAP_MINUTES

    @property
    def total_lead_hours(self) -> float:
        return self.unique_lead_seconds / 3600.0

    @property
    def total_trail_hours(self) -> float:
        return self.unique_trail_seconds / 3600.0

    @property
    def total_edge_hours(self) -> float:
        return self.unique_edge_seconds / 3600.0

    @property
    def capped_edge_hours(self) -> float:
        return self.capped_edge_seconds / 3600.0

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable summary (no hour mutation — diagnostics only)."""
        if not self.available:
            return {
                "available": False,
                "reason": self.reason or "no span-level presence",
                "label": "presence_edge_gaps",
                "note": "Diagnostic only; does not change observed hours (GH-332 Slice 1).",
            }
        return {
            "available": True,
            "presence_source": self.presence_source,
            "total_lead_hours": round(self.total_lead_hours, 6),
            "total_trail_hours": round(self.total_trail_hours, 6),
            "total_edge_hours": round(self.total_edge_hours, 6),
            "capped_edge_hours": round(self.capped_edge_hours, 6),
            "edge_cap_minutes": self.edge_cap_minutes,
            "session_count_with_edge": sum(1 for s in self.sessions if s.edge_seconds > 0),
            "sessions": [
                {
                    "day": s.day,
                    "session_index": s.session_index,
                    "start": s.session_start.isoformat(),
                    "end": s.session_end.isoformat(),
                    "lead_hours": round(s.lead_seconds / 3600.0, 6),
                    "trail_hours": round(s.trail_seconds / 3600.0, 6),
                    "edge_hours": round(s.edge_seconds / 3600.0, 6),
                }
                for s in self.sessions
                if s.edge_seconds > 0
            ],
            "label": "presence_edge_gaps",
            "note": (
                "Unique wall-clock of continuous presence adjacent to evidenced "
                "session edges (lead/trail). Totals are de-overlapped; capped_* "
                "applies the Slice 2 default per-edge cap. Diagnostic only — does "
                "not change observed hours (GH-332 Slice 1)."
            ),
        }


def _merge_presence_spans(
    spans: Sequence[tuple[datetime, datetime]],
    *,
    bridge_seconds: int,
) -> list[tuple[datetime, datetime]]:
    """Merge overlapping/abutting presence spans (bridge short stalls)."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda pair: pair[0])
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    bridge = timedelta(seconds=max(0, bridge_seconds))
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + bridge:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _merge_intervals(
    intervals: Sequence[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda pair: pair[0])
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for start, end in ordered[1:]:
        if end <= start:
            continue
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _interval_seconds(intervals: Sequence[tuple[datetime, datetime]]) -> float:
    return sum(max(0.0, (end - start).total_seconds()) for start, end in intervals)


def _covering_presence(
    ts: datetime,
    presence_spans: Sequence[tuple[datetime, datetime]],
) -> tuple[datetime, datetime] | None:
    """Return the presence span covering ``ts``, if any.

    Spans are ``(start, end_exclusive)`` — same contract as Timely Memory.
    """
    for p_start, p_end in presence_spans:
        if p_start <= ts < p_end:
            return p_start, p_end
    return None


def _session_bounds(
    overall_days: Dict[str, Any],
) -> list[tuple[str, int, datetime, datetime]]:
    """Flatten sessions as (day, index, start, end), sorted by start."""
    rows: list[tuple[str, int, datetime, datetime]] = []
    for day in sorted(overall_days.keys()):
        for idx, s_tuple in enumerate((overall_days[day].get("sessions") or []), start=1):
            start_ts, end_ts = s_tuple[0], s_tuple[1]
            if isinstance(start_ts, datetime) and isinstance(end_ts, datetime):
                rows.append((day, idx, start_ts, end_ts))
    rows.sort(key=lambda row: row[2])
    return rows


def _clip_edge_interval(
    start: datetime,
    end: datetime,
    *,
    floor: datetime | None,
    ceiling: datetime | None,
) -> tuple[datetime, datetime] | None:
    """Clip [start, end) to (floor, ceiling); None if empty."""
    if end <= start:
        return None
    lo = start if floor is None else max(start, floor)
    hi = end if ceiling is None else min(end, ceiling)
    if hi <= lo:
        return None
    return lo, hi


def measure_session_edge_gaps(
    overall_days: Dict[str, Any],
    presence_spans: Sequence[tuple[datetime, datetime]] | None,
    *,
    presence_source: str = "Timely Memory",
    bridge_seconds: int = DEFAULT_PRESENCE_BRIDGE_SECONDS,
    edge_cap_minutes: int = DEFAULT_EDGE_CAP_MINUTES,
) -> EdgeGapReport:
    """Compute lead/trail presence adjacent to each evidenced session.

    Does not mutate ``overall_days`` or session timestamps. Totals use unique
    wall-clock of edge intervals (clipped so they do not enter other sessions).
    """
    if not presence_spans:
        return EdgeGapReport(
            available=False,
            reason="no span-level presence (enable --timely-memory-source on)",
        )

    merged = _merge_presence_spans(presence_spans, bridge_seconds=bridge_seconds)
    sessions = _session_bounds(overall_days)
    sessions_out: list[SessionEdgeGap] = []
    lead_intervals: list[tuple[datetime, datetime]] = []
    trail_intervals: list[tuple[datetime, datetime]] = []
    capped_intervals: list[tuple[datetime, datetime]] = []
    cap = timedelta(minutes=max(0, edge_cap_minutes))

    for i, (day, idx, start_ts, end_ts) in enumerate(sessions):
        prev_end = sessions[i - 1][3] if i > 0 else None
        next_start = sessions[i + 1][2] if i + 1 < len(sessions) else None

        lead_seconds = 0.0
        trail_seconds = 0.0

        covering_start = _covering_presence(start_ts, merged)
        if covering_start is not None:
            p_start, p_end = covering_start
            # Continuous presence across the previous session: the between-gap is
            # that session's trail — do not also count it as this session's lead.
            if prev_end is not None and p_start <= prev_end < p_end:
                clipped_lead = None
            else:
                clipped_lead = _clip_edge_interval(
                    p_start, start_ts, floor=prev_end, ceiling=start_ts
                )
            if clipped_lead is not None:
                lead_intervals.append(clipped_lead)
                lead_seconds = (clipped_lead[1] - clipped_lead[0]).total_seconds()
                capped = _clip_edge_interval(
                    start_ts - cap, start_ts, floor=clipped_lead[0], ceiling=start_ts
                )
                if capped is not None:
                    capped_intervals.append(capped)

        covering_end = _covering_presence(end_ts, merged)
        if covering_end is not None:
            _p_start, p_end = covering_end
            clipped = _clip_edge_interval(
                end_ts, p_end, floor=end_ts, ceiling=next_start
            )
            if clipped is not None:
                trail_intervals.append(clipped)
                trail_seconds = (clipped[1] - clipped[0]).total_seconds()
                capped = _clip_edge_interval(
                    end_ts, end_ts + cap, floor=end_ts, ceiling=clipped[1]
                )
                if capped is not None:
                    capped_intervals.append(capped)

        sessions_out.append(
            SessionEdgeGap(
                day=day,
                session_index=idx,
                session_start=start_ts,
                session_end=end_ts,
                lead_seconds=lead_seconds,
                trail_seconds=trail_seconds,
                presence_source=presence_source,
            )
        )

    unique_leads = _merge_intervals(lead_intervals)
    unique_trails = _merge_intervals(trail_intervals)
    unique_all = _merge_intervals([*unique_leads, *unique_trails])
    unique_capped = _merge_intervals(capped_intervals)

    return EdgeGapReport(
        available=True,
        presence_source=presence_source,
        sessions=sessions_out,
        unique_lead_seconds=_interval_seconds(unique_leads),
        unique_trail_seconds=_interval_seconds(unique_trails),
        unique_edge_seconds=_interval_seconds(unique_all),
        capped_edge_seconds=_interval_seconds(unique_capped),
        edge_cap_minutes=edge_cap_minutes,
    )
