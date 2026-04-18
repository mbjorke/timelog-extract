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
    Determine whether Toggl API collection should run and, if not, provide a disable reason.
    
    Checks the configured `toggl_source` mode (`auto`, `on`, or `off`) and whether an API token is available to decide enablement; returns a human-readable disable reason when disabled.
    
    Parameters:
        args (Any): Object providing CLI/config values (expects `toggl_source` and may provide `toggl_api_token` or rely on TOGGL_API_TOKEN env).
    
    Returns:
        tuple[bool, Optional[str]]: A pair where the first element is `True` when collection is enabled and `False` otherwise; the second element is a disable reason string when disabled, or `None` when enabled.
    """
    mode = str(getattr(args, "toggl_source", "auto") or "auto").strip().lower()
    if mode not in ("auto", "on", "off"):
        return False, f"invalid toggl_source mode '{mode}' (expected auto/on/off)"
    if mode == "off":
        return False, "Toggl source disabled via toggl_source=off"
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
    Collect Toggl workspace events.
    
    Currently a placeholder that logs a warning and returns an empty list; actual Toggl API collection is not implemented.
    
    Returns:
        list[dict[str, Any]]: A list of event dictionaries; currently always empty.
    """
    logging.warning("Toggl collector is a placeholder; collect_workspace_events returns no events")
    return []
