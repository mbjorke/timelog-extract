"""Toggl API source gating, collection, and time-entry posting helpers."""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class _RejectHttpRedirectHandler(HTTPRedirectHandler):
    """Block redirects to plain HTTP so Authorization headers are never forwarded."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlparse
        if (urlparse(newurl).scheme or "").lower() == "http":
            raise URLError("Toggl redirect to insecure http:// rejected to protect credentials")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_toggl_opener = build_opener(_RejectHttpRedirectHandler(), HTTPSHandler())


def urlopen(req: Request, timeout: int = 20):
    return _toggl_opener.open(req, timeout=timeout)


TOGGL_API_BASE = "https://api.track.toggl.com"


def resolve_toggl_api_token(args: Any) -> str:
    """Resolve Toggl API token from CLI arg override or environment."""
    explicit = getattr(args, "toggl_api_token", None)
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    return (os.environ.get("TOGGL_API_TOKEN") or "").strip()


@dataclass
class TogglCredentials:
    """Auth + default workspace for posting time entries to Toggl."""

    api_token: str
    workspace_id: int


def resolve_toggl_workspace_id(args: Any) -> Optional[int]:
    """Resolve the default Toggl workspace id from CLI arg override or environment."""
    explicit = getattr(args, "toggl_workspace_id", None)
    raw = explicit if (explicit not in (None, "")) else os.environ.get("TOGGL_WORKSPACE_ID")
    if raw in (None, ""):
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def resolve_toggl_credentials(args: Any) -> Optional[TogglCredentials]:
    """Return TogglCredentials when both an API token and workspace id are available."""
    token = resolve_toggl_api_token(args)
    workspace_id = resolve_toggl_workspace_id(args)
    if not token or workspace_id is None:
        return None
    return TogglCredentials(api_token=token, workspace_id=workspace_id)


def toggl_sync_enabled(args: Any) -> tuple[bool, Optional[str]]:
    """
    Determine whether Toggl time-entry posting should run and, if not, why.

    Mirrors the Jira sync gating: respects an `auto`/`on`/`off` `toggl_sync`
    mode and requires both an API token and a workspace id to be configured.
    """
    mode = str(getattr(args, "toggl_sync", "auto") or "auto").strip().lower()
    if mode not in ("auto", "on", "off"):
        return False, f"invalid toggl_sync mode '{mode}' (expected auto/on/off)"
    if mode == "off":
        return False, "Toggl sync disabled via toggl_sync=off"
    creds = resolve_toggl_credentials(args)
    if creds is None:
        hint = "set TOGGL_API_TOKEN and TOGGL_WORKSPACE_ID"
        if mode == "on":
            return False, f"Toggl sync on but credentials missing ({hint})"
        return False, f"no Toggl credentials ({hint})"
    return True, None


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


def _toggl_auth_header(api_token: str) -> str:
    raw = f"{api_token}:api_token".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _toggl_request(creds: TogglCredentials, method: str, path: str, payload: Optional[dict] = None) -> Any:
    url = f"{TOGGL_API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", _toggl_auth_header(creds.api_token))
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Toggl HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Toggl network error: {exc.reason}") from exc
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Toggl returned a non-JSON response") from exc


def build_time_entry_payload(
    creds: TogglCredentials,
    start: datetime,
    duration_seconds: int,
    description: str,
    project_id: int,
    tags: Optional[List[str]] = None,
) -> dict:
    """
    Build the exact Toggl v9 time-entry POST body.

    Shared by the live POST and the dry-run preview so the payload printed
    before a network call is byte-for-byte what would be sent.

    Raises:
        RuntimeError: If `start` lacks a timezone offset.
    """
    if start.tzinfo is None or start.utcoffset() is None:
        raise RuntimeError("Toggl time entry 'start' must include timezone offset")
    # Toggl v9 requires RFC3339 with a colon in the offset (e.g. +03:00) or "Z";
    # datetime.isoformat() produces the colon form, unlike strftime("%z").
    return {
        "start": start.replace(microsecond=0).isoformat(),
        "duration": int(duration_seconds),
        "description": description,
        "project_id": int(project_id),
        "workspace_id": creds.workspace_id,
        "created_with": "gittan",
        "tags": list(tags or []),
    }


def post_toggl_time_entry(
    creds: TogglCredentials,
    start: datetime,
    duration_seconds: int,
    description: str,
    project_id: int,
    tags: Optional[List[str]] = None,
) -> str:
    """
    Create a Toggl time entry and return its id.

    Parameters:
        creds: Toggl credentials including the destination workspace id.
        start: When the work started; must include a timezone offset.
        duration_seconds: Duration of the entry in seconds.
        description: Free-text description shown in Toggl.
        project_id: Toggl numeric project id to attach the entry to.
        tags: Optional tags (used for the gittan idempotency marker).

    Raises:
        RuntimeError: If `start` lacks tz offset, the request fails, or the
            response is missing an entry id.
    """
    payload = build_time_entry_payload(
        creds, start, duration_seconds, description, project_id, tags
    )
    parsed = _toggl_request(
        creds,
        "POST",
        f"/api/v9/workspaces/{creds.workspace_id}/time_entries",
        payload,
    )
    if not isinstance(parsed, dict):
        raise RuntimeError("Toggl returned an unexpected (non-object) response for time entry create")
    entry_id = str(parsed.get("id") or "").strip()
    if not entry_id:
        raise RuntimeError("Toggl response missing time entry id")
    return entry_id


def delete_toggl_time_entry(
    creds: TogglCredentials, entry_id: str, workspace_id: Optional[int] = None
) -> str:
    """Delete a Toggl time entry by id (for op-log rollback).

    ``workspace_id`` targets the workspace the entry actually lives in — the
    rollback flow passes the id recorded in the op-log row, not the currently
    configured default, so a run with a different active workspace cannot delete
    the wrong entry or falsely report success. Falls back to ``creds.workspace_id``.

    Returns ``"deleted"`` on success or ``"gone"`` when Toggl reports the entry
    no longer exists (HTTP 404) — the latter is treated as an idempotent success
    by the rollback flow, since the desired end state (entry absent) already
    holds. Any other failure raises ``RuntimeError``.
    """
    wid = workspace_id if workspace_id is not None else creds.workspace_id
    try:
        _toggl_request(
            creds,
            "DELETE",
            f"/api/v9/workspaces/{wid}/time_entries/{entry_id}",
        )
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return "gone"
        raise
    return "deleted"


def list_toggl_time_entries(creds: TogglCredentials, start_date: str, end_date: str) -> List[dict]:
    """
    List the authenticated user's Toggl time entries within an inclusive date window.

    Parameters:
        start_date / end_date: ``YYYY-MM-DD`` bounds passed straight to Toggl.

    Returns:
        A list of time-entry dicts (may be empty); each typically carries a
        ``tags`` list used for duplicate detection.
    """
    parsed = _toggl_request(
        creds,
        "GET",
        f"/api/v9/me/time_entries?start_date={start_date}&end_date={end_date}",
    )
    if not isinstance(parsed, list):
        return []
    return [entry for entry in parsed if isinstance(entry, dict)]


def verify_toggl_credentials(creds: TogglCredentials) -> tuple[bool, str, str]:
    """
    Check Toggl credentials live via ``GET /api/v9/me``.

    Returns ``(ok, detail, suspect)``. ``detail`` names the authenticated account
    on success or the failure reason. ``suspect`` is ``"credentials"`` when the
    token is rejected, else ``""``. Never raises.
    """
    try:
        data = _toggl_request(creds, "GET", "/api/v9/me")
    except RuntimeError as exc:
        msg = str(exc)
        if "401" in msg or "403" in msg:
            return False, "API token rejected", "credentials"
        return False, msg, ""
    if not isinstance(data, dict):
        return False, "Toggl returned an unexpected response", ""
    who = data.get("fullname") or data.get("email") or "the account"
    return True, f"authenticated as {who}", ""
