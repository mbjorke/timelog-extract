"""Shared test helpers for collector event shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any


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
    clean = {
        str(kind): str(value).strip().lower()
        for kind, value in (anchors or {}).items()
        if kind and value and str(value).strip()
    }
    if clean:
        event["anchors"] = clean
    return event
