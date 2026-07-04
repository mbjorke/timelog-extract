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

from core.timely_memory import collect_timely_memory, timely_memory_db_candidates
from core.report_runtime import collect_screen_time_status, collect_timely_memory_status
from core.screen_time import collect_screen_time

APPLE_EPOCH = 978307200


def screen_time_db_candidates(home: Path) -> list[Path]:
    return [
        home / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db",
        home / "Library" / "Application Support" / "KnowledgeC" / "knowledgeC.db",
    ]


def collect_presence_comparators(
    *,
    args: argparse.Namespace,
    dt_from: datetime,
    dt_to: datetime,
    collector_status: Dict[str, Dict[str, Any]],
    home: Path,
    local_tz,
    want_log_fn: Callable[[argparse.Namespace], bool],
) -> Optional[Dict[str, float]]:
    """Run both presence comparators; returns Screen Time daily seconds."""
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
    collect_timely_memory_status(
        args=args,
        dt_from=dt_from,
        dt_to=dt_to,
        collector_status=collector_status,
        collect_timely_memory_fn=lambda a, b: collect_timely_memory(
            a, b, candidates=timely_memory_db_candidates(home), local_tz=local_tz
        ),
    )
    return screen_time_days
