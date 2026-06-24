"""Shared test helpers for collector event shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.events import _normalize_anchor_value


def make_test_event(
    source: str,
    ts: datetime,
    detail: str,
    project: str,
    anchors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a test event with the same anchor normalization as ``core.events.make_event``."""
    event: dict[str, Any] = {
        "source": source,
        "timestamp": ts,
        "detail": detail,
        "project": project,
    }
    clean = {}
    for kind, value in (anchors or {}).items():
        if not kind:
            continue
        normalized = _normalize_anchor_value(str(kind), value)
        if normalized:
            clean[str(kind)] = normalized
    if clean:
        event["anchors"] = clean
    return event
