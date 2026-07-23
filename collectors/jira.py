"""Jira auth helpers and worklog POST client."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class _RejectHttpRedirectHandler(HTTPRedirectHandler):
    """Block redirects to plain HTTP so Authorization headers are never forwarded."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if (urlparse(newurl).scheme or "").lower() == "http":
            raise URLError(
                "Jira redirect to insecure http:// rejected to protect credentials"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_jira_opener = build_opener(_RejectHttpRedirectHandler(), HTTPSHandler())


def urlopen(req: Request, timeout: int = 20):
    return _jira_opener.open(req, timeout=timeout)


class JiraApiError(RuntimeError):
    """A Jira API call failed. ``status`` is the HTTP code when there was one
    (``None`` for network/transport errors), so callers can branch — e.g. treat a
    404 as "issue not found / no access" rather than a fatal error."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


@dataclass
class JiraCredentials:
    base_url: str
    email: str
    api_token: str


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def jira_site_label(base_url: str) -> str:
    """Return hostname for display; never userinfo from a misconfigured URL."""
    from urllib.parse import urlparse

    raw = (base_url or "").strip()
    if not raw:
        return ""
    host = (urlparse(raw).hostname or "").strip()
    if host:
        return host
    # Scheme-less or malformed URLs may embed userinfo; never echo the raw value.
    tail = raw.rsplit("@", 1)[-1].strip()
    if tail and tail != raw:
        return tail.split("/", 1)[0]
    return ""


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


def verify_jira_credentials(creds: JiraCredentials) -> tuple[bool, str, str]:
    """
    Check Jira credentials live via ``GET /rest/api/3/myself``.

    Returns ``(ok, detail, suspect)``. ``detail`` names the authenticated account
    on success or the failure reason. ``suspect`` classifies which input is most
    likely wrong so the caller can re-prompt just that: ``"url"`` (bad/unreachable
    base URL), ``"credentials"`` (email/token rejected), or ``""`` (ok/unknown).
    Never raises.
    """
    low = creds.base_url.lower()
    if low.startswith("http://"):
        return False, "base URL must use https:// (a token over plain http is insecure)", "url"
    if not low.startswith("https://"):
        return False, "base URL should start with https://", "url"
    url = f"{creds.base_url}/rest/api/3/myself"
    req = Request(url, method="GET")
    req.add_header("Authorization", _jira_auth_header(creds.email, creds.api_token))
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code in (401, 403):
            return False, f"email/token rejected (HTTP {exc.code})", "credentials"
        if exc.code == 404:
            return False, "no Jira API at this URL (HTTP 404)", "url"
        return False, f"Jira HTTP {exc.code}", ""
    except URLError as exc:
        return False, f"could not reach Jira ({exc.reason})", "url"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False, "Jira returned a non-JSON response", "url"
    who = data.get("emailAddress") or data.get("displayName") or "the account"
    return True, f"authenticated as {who}", ""


def adf_comment_text(comment: Any) -> str:
    """
    Extract plain text from a Jira worklog comment for marker matching.

    Jira worklog comments are normally Atlassian Document Format (ADF) docs, but
    older/edge responses may hand back a plain string, ``None``, or unexpected
    shapes. This walks any nested ``content``/``text`` structure defensively and
    returns the concatenated plain text; anything it cannot interpret yields
    ``""`` rather than raising.
    """
    if comment is None:
        return ""
    if isinstance(comment, str):
        return comment
    parts: List[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str):
                parts.append(text)
            _walk(node.get("content"))
        elif isinstance(node, list):
            for child in node:
                _walk(child)

    _walk(comment)
    return " ".join(parts)


def list_jira_worklogs(creds: JiraCredentials, issue_key: str) -> List[dict]:
    """
    Fetch all existing worklogs for an issue, following pagination.

    ``GET /rest/api/3/issue/{key}/worklog`` returns one page
    (``startAt``/``maxResults``/``total``); this follows subsequent pages so a
    marker on a later page is never missed during dedup.

    Raises:
        ValueError: If base URL is not HTTPS.
        JiraApiError: If an HTTP request fails (``.status`` carries the HTTP code,
            or ``None`` for a network error) or Jira returns a non-JSON response.
    """
    if not creds.base_url.lower().startswith("https://"):
        raise ValueError("Jira base URL must use HTTPS to prevent credential leakage over unencrypted HTTP")
    base = f"{creds.base_url}/rest/api/3/issue/{quote(issue_key, safe='')}/worklog"
    collected: List[dict] = []
    start_at = 0
    while True:
        url = f"{base}?startAt={start_at}"
        req = Request(url, method="GET")
        req.add_header("Authorization", _jira_auth_header(creds.email, creds.api_token))
        req.add_header("Accept", "application/json")
        try:
            with urlopen(req, timeout=20) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise JiraApiError(f"Jira HTTP {exc.code}: {detail}", status=exc.code) from exc
        except URLError as exc:
            raise JiraApiError(f"Jira network error: {exc.reason}", status=None) from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise JiraApiError("Jira returned non-JSON response for worklog list", status=None) from exc
        worklogs = parsed.get("worklogs")
        page = list(worklogs) if isinstance(worklogs, list) else []
        collected.extend(page)
        total = parsed.get("total")
        # Stop when we've seen everything, or when a page returns nothing (guard
        # against a missing/short total looping forever).
        if not page or not isinstance(total, int) or len(collected) >= total:
            break
        start_at = len(collected)
    return collected


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
        ValueError: If base URL is not HTTPS.
        RuntimeError: If `started` lacks timezone offset.
        RuntimeError: If the HTTP request fails (network error or non-2xx response).
        RuntimeError: If Jira returns a non-JSON response or the response is missing the worklog id.
    """
    if not creds.base_url.lower().startswith("https://"):
        raise ValueError("Jira base URL must use HTTPS to prevent credential leakage over unencrypted HTTP")
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
