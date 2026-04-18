"""Jira auth helpers and worklog POST client."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass
class JiraCredentials:
    base_url: str
    email: str
    api_token: str


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def resolve_jira_credentials(args: Any) -> Optional[JiraCredentials]:
    base_url = (
        (getattr(args, "jira_base_url", None) or os.environ.get("JIRA_BASE_URL") or "")
        .strip()
    )
    email = (
        (getattr(args, "jira_email", None) or os.environ.get("JIRA_EMAIL") or "")
        .strip()
    )
    api_token = (
        (getattr(args, "jira_api_token", None) or os.environ.get("JIRA_API_TOKEN") or "")
        .strip()
    )
    if not base_url or not email or not api_token:
        return None
    return JiraCredentials(
        base_url=_normalize_base_url(base_url),
        email=email,
        api_token=api_token,
    )


def jira_sync_enabled(args: Any) -> tuple[bool, Optional[str]]:
    mode = str(getattr(args, "jira_sync", "auto") or "auto").strip().lower()
    if mode == "off":
        return False, "Jira sync disabled via jira_sync=off"
    creds = resolve_jira_credentials(args)
    if mode == "on" and creds is None:
        return False, "Jira sync on but credentials missing (set JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN)"
    if mode == "auto" and creds is None:
        return False, "no Jira credentials (set JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN)"
    if creds is None:
        return False, "no Jira credentials"
    return True, None


def _jira_auth_header(email: str, api_token: str) -> str:
    raw = f"{email}:{api_token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def post_jira_worklog(
    creds: JiraCredentials,
    issue_key: str,
    started: datetime,
    time_spent_seconds: int,
    comment: str,
) -> str:
    """
    Create a worklog on a Jira issue and return the created worklog's id.
    
    Parameters:
        creds (JiraCredentials): Jira connection and authentication information.
        issue_key (str): Issue key to attach the worklog to (will be URL-encoded).
        started (datetime): Timestamp when the work was started; must include a timezone offset.
        time_spent_seconds (int): Duration of the work in seconds.
        comment (str): Plain-text comment to include in the worklog.
    
    Returns:
        worklog_id (str): The id of the created worklog.
    
    Raises:
        RuntimeError: If `started` lacks timezone offset.
        RuntimeError: If the HTTP request fails (network error or non-2xx response).
        RuntimeError: If Jira returns a non-JSON response or the response is missing the worklog id.
    """
    if started.tzinfo is None or started.utcoffset() is None:
        raise RuntimeError("Jira worklog 'started' must include timezone offset")
    payload = {
        "started": started.strftime("%Y-%m-%dT%H:%M:%S.000%z"),
        "timeSpentSeconds": int(time_spent_seconds),
        "comment": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]},
    }
    url = f"{creds.base_url}/rest/api/3/issue/{quote(issue_key, safe='')}/worklog"
    req = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Authorization", _jira_auth_header(creds.email, creds.api_token))
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jira HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Jira network error: {exc.reason}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise RuntimeError("Jira returned non-JSON response for worklog create")
    worklog_id = str(parsed.get("id") or "").strip()
    if not worklog_id:
        raise RuntimeError("Jira response missing worklog id")
    return worklog_id
