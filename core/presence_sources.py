"""Presence-comparator sources (coverage_comparator role) for report runs.

Owns the bound collectors and status calls for sources that measure presence
rather than work evidence: Screen Time and the opt-in Timely Memory buffer.
They report per-day presence context via ``collector_status`` and never enter
the event pipeline, so they cannot create classified project time.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.report_runtime import collect_screen_time_status
from core.screen_time import collect_screen_time
from core.timely_memory import (
    TIMELY_MEMORY_SOURCE,
    collect_timely_memory,
    timely_memory_db_candidates,
    timely_memory_source_enabled,
)

APPLE_EPOCH = 978307200


def screen_time_db_candidates(home: Path) -> list[Path]:
    return [
        home / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db",
        home / "Library" / "Application Support" / "KnowledgeC" / "knowledgeC.db",
    ]


def collect_timely_memory_status(
    *,
    args: argparse.Namespace,
    dt_from: datetime,
    dt_to: datetime,
    collector_status: Dict[str, Dict[str, Any]],
    collect_timely_memory_fn: Callable[[datetime, datetime], Any],
) -> tuple[Optional[Dict[str, float]], Optional[list]]:
    """Opt-in presence comparator (coverage_comparator role, like Screen Time).

    Off by default: nothing is read unless --timely-memory-source on. Returns
    ``(daily_seconds, spans)`` — context only; never enters the event pipeline.
    Spans are ``(start, end_exclusive)`` UTC datetimes for GH-332 edge-gap
    diagnostics; they cannot create classified project time.
    """
    enabled, reason = timely_memory_source_enabled(args)
    if not enabled:
        collector_status[TIMELY_MEMORY_SOURCE] = {
            "enabled": False,
            "reason": reason,
            "days": 0,
        }
        return None, None

    collected = collect_timely_memory_fn(dt_from, dt_to)
    # Accept legacy 2-tuple (days, msg) or 3-tuple (days, msg, spans).
    if not isinstance(collected, tuple) or len(collected) < 2:
        collector_status[TIMELY_MEMORY_SOURCE] = {
            "enabled": True,
            "reason": "invalid Timely Memory collector result",
            "days": 0,
        }
        return None, None
    memory_days, memory_msg = collected[0], collected[1]
    memory_spans = collected[2] if len(collected) > 2 else None
    if memory_days is None:
        collector_status[TIMELY_MEMORY_SOURCE] = {
            "enabled": True,
            "reason": memory_msg,
            "days": 0,
        }
        return None, None

    collector_status[TIMELY_MEMORY_SOURCE] = {
        "enabled": True,
        "reason": "",
        "days": len(memory_days),
        "presence_hours": round(sum(memory_days.values()) / 3600.0, 2),
        "span_count": len(memory_spans or []),
    }
    return memory_days, memory_spans


def collect_presence_comparators(
    *,
    args: argparse.Namespace,
    dt_from: datetime,
    dt_to: datetime,
    collector_status: Dict[str, Dict[str, Any]],
    home: Path,
    local_tz,
    want_log_fn: Callable[[argparse.Namespace], bool],
) -> tuple[Optional[Dict[str, float]], Optional[list]]:
    """Run both presence comparators.

    Returns ``(screen_time_daily_seconds, timely_memory_spans)``. Spans are
    Timely Memory ``(start, end_exclusive)`` edges for GH-332 diagnostics when
    ``--timely-memory-source on``; otherwise ``None``.
    """
    screen_time_days = collect_screen_time_status(
        args=args,
        dt_from=dt_from,
        dt_to=dt_to,
        collector_status=collector_status,
        collect_screen_time_fn=lambda a, b: collect_screen_time(
            a,
            b,
            candidates=screen_time_db_candidates(home),
            apple_epoch=APPLE_EPOCH,
            local_tz=local_tz,
        ),
        want_log_fn=want_log_fn,
    )
    _memory_days, memory_spans = collect_timely_memory_status(
        args=args,
        dt_from=dt_from,
        dt_to=dt_to,
        collector_status=collector_status,
        collect_timely_memory_fn=lambda a, b: collect_timely_memory(
            a, b, candidates=timely_memory_db_candidates(home), local_tz=local_tz
        ),
    )
    return screen_time_days, memory_spans
