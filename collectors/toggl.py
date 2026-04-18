"""Toggl API source gating and collection helpers."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional


def resolve_toggl_api_token(args: Any) -> str:
    """Resolve Toggl API token from CLI arg override or environment."""
    explicit = getattr(args, "toggl_api_token", None)
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    return (os.environ.get("TOGGL_API_TOKEN") or "").strip()


def toggl_source_enabled(args: Any) -> tuple[bool, Optional[str]]:
    """
    Return (enabled, disable_reason) for Toggl API collection.

    Defaults to auto mode so the source is enabled when credentials exist and
    disabled with a clear reason otherwise.
    """
    mode = str(getattr(args, "toggl_source", "auto") or "auto").strip().lower()
    if mode == "off":
        return False, "Toggl source disabled via toggl_source=off"
    if mode not in ("off", "on", "auto"):
        return False, f"Unknown toggl_source mode: {mode!r} (expected: auto/on/off)"
    token = resolve_toggl_api_token(args)
    if mode == "on" and not token:
        return False, "Toggl on but no API token (set TOGGL_API_TOKEN)"
    if mode == "auto" and not token:
        return False, "no Toggl API token (set TOGGL_API_TOKEN for this source)"
    if not token:
        return False, "no Toggl API token"
    return True, None


def collect_workspace_events(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """
    Placeholder for Toggl API event collection.

    The auto-detect toggle is wired now; collector logic can be expanded later.

    TODO: implement actual Toggl time entry collection
    """
    logging.warning("Toggl collector is a placeholder stub; returning no events")
    return []
