"""Measure adjacent presence at evidenced session edges (GH-332 Slice 1).

Diagnostics only: does **not** stretch sessions or change observed hours.
When Timely Memory (or another span-level presence source) shows continuous
presence immediately before the first event or after the last, report how many
minutes that edge gap covers. Slice 2 (bracketing) will optionally extend
spans using these measurements, with a cap + label.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Sequence

# Bridge short stalls the same way Timely Memory folds samples into spans.
DEFAULT_PRESENCE_BRIDGE_SECONDS = 30


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

    @property
    def total_lead_hours(self) -> float:
        return sum(s.lead_seconds for s in self.sessions) / 3600.0

    @property
    def total_trail_hours(self) -> float:
        return sum(s.trail_seconds for s in self.sessions) / 3600.0

    @property
    def total_edge_hours(self) -> float:
        return self.total_lead_hours + self.total_trail_hours

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
                "Adjacent continuous presence before/after evidenced sessions. "
                "Diagnostic only — does not change observed hours (GH-332 Slice 1)."
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


def _lead_seconds(
    session_start: datetime,
    presence_spans: Sequence[tuple[datetime, datetime]],
) -> float:
    """Seconds of continuous presence ending at/covering session_start, before it."""
    for p_start, p_end in presence_spans:
        if p_start <= session_start <= p_end:
            return max(0.0, (session_start - p_start).total_seconds())
    return 0.0


def _trail_seconds(
    session_end: datetime,
    presence_spans: Sequence[tuple[datetime, datetime]],
) -> float:
    """Seconds of continuous presence starting at/covering session_end, after it."""
    for p_start, p_end in presence_spans:
        if p_start <= session_end <= p_end:
            return max(0.0, (p_end - session_end).total_seconds())
    return 0.0


def measure_session_edge_gaps(
    overall_days: Dict[str, Any],
    presence_spans: Sequence[tuple[datetime, datetime]] | None,
    *,
    presence_source: str = "Timely Memory",
    bridge_seconds: int = DEFAULT_PRESENCE_BRIDGE_SECONDS,
) -> EdgeGapReport:
    """Compute lead/trail presence adjacent to each evidenced session.

    Does not mutate ``overall_days`` or session timestamps.
    """
    if not presence_spans:
        return EdgeGapReport(
            available=False,
            reason="no span-level presence (enable --timely-memory-source on)",
        )

    merged = _merge_presence_spans(presence_spans, bridge_seconds=bridge_seconds)
    sessions_out: list[SessionEdgeGap] = []
    for day in sorted(overall_days.keys()):
        payload = overall_days[day]
        for idx, s_tuple in enumerate(payload.get("sessions") or [], start=1):
            start_ts, end_ts = s_tuple[0], s_tuple[1]
            if not isinstance(start_ts, datetime) or not isinstance(end_ts, datetime):
                continue
            sessions_out.append(
                SessionEdgeGap(
                    day=day,
                    session_index=idx,
                    session_start=start_ts,
                    session_end=end_ts,
                    lead_seconds=_lead_seconds(start_ts, merged),
                    trail_seconds=_trail_seconds(end_ts, merged),
                    presence_source=presence_source,
                )
            )

    return EdgeGapReport(
        available=True,
        presence_source=presence_source,
        sessions=sessions_out,
    )
