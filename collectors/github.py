"""GitHub public activity via REST API (optional; requires username)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class _RejectHttpRedirectHandler(HTTPRedirectHandler):
    """Block redirects to plain HTTP so Authorization headers are never forwarded."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlparse
        if (urlparse(newurl).scheme or "").lower() == "http":
            raise URLError("GitHub redirect to insecure http:// rejected to protect credentials")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_github_opener = build_opener(_RejectHttpRedirectHandler(), HTTPSHandler())


def urlopen(req: Request, timeout: int = 30):
    return _github_opener.open(req, timeout=timeout)


from core.cli_options import package_version
from core.sources import GITHUB_SOURCE

USER_AGENT = (
    f"timelog-extract/{package_version()} "
    "(+https://github.com/mbjorke/timelog-extract)"
)
PER_PAGE = 100
MAX_PAGES = 10

DEFAULT_GITHUB_API_BASE = "https://api.github.com"
_ENV_API_BASE = "GITHUB_API_BASE_URL"


def resolve_github_api_base() -> str:
    """REST API root: github.com uses https://api.github.com; Enterprise Server uses https://host/api/v3."""
    raw = (os.environ.get(_ENV_API_BASE) or "").strip()
    base = raw or DEFAULT_GITHUB_API_BASE
    return base.rstrip("/")


def _split_logins(raw: str) -> List[str]:
    if not raw or not raw.strip():
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def resolve_github_usernames(args: Any) -> List[str]:
    """CLI `--github-user` (comma-separated) overrides `GITHUB_USER` / `GITHUB_LOGIN` (comma-separated)."""
    explicit = getattr(args, "github_user", None)
    if explicit is not None and str(explicit).strip():
        return _split_logins(str(explicit))
    env = (os.environ.get("GITHUB_USER") or os.environ.get("GITHUB_LOGIN") or "").strip()
    return _split_logins(env)


def resolve_github_username(args: Any) -> str:
    """First GitHub login, or empty (backward compatibility for single-user callers)."""
    users = resolve_github_usernames(args)
    return users[0] if users else ""


def github_source_enabled(args: Any) -> tuple[bool, Optional[str]]:
    """Return (enabled, disable_reason)."""
    mode = getattr(args, "github_source", "auto")
    if mode == "off":
        return False, "GitHub source disabled via --github-source off"
    users = resolve_github_usernames(args)
    if mode == "on" and not users:
        return False, "GitHub on but no username (use --github-user or GITHUB_USER)"
    if mode == "auto" and not users:
        return False, "no GitHub username (set --github-user or GITHUB_USER for this source)"
    if not users:
        return False, "no GitHub username"
    return True, None


def _parse_github_ts(created_at: str) -> datetime:
    if created_at.endswith("Z"):
        created_at = created_at[:-1] + "+00:00"
    return datetime.fromisoformat(created_at)


def _detail_for_event(ev: Dict[str, Any]) -> str:
    et = ev.get("type") or "unknown"
    repo = (ev.get("repo") or {}).get("name") or "unknown/repo"
    payload = ev.get("payload") or {}

    if et == "PushEvent":
        commits = payload.get("commits") or []
        n = len(commits) if commits else payload.get("size") or 0
        ref = (payload.get("ref") or "").split("/")[-1] or "default"
        return f"push to {repo} ({n} commits, ref {ref})"

    if et == "PullRequestEvent":
        pr = payload.get("pull_request") or {}
        title = (pr.get("title") or "").strip() or "(no title)"
        action = payload.get("action") or "?"
        num = pr.get("number", "")
        return f"PR #{num} {action}: {title} ({repo})"

    if et == "IssuesEvent":
        issue = payload.get("issue") or {}
        title = (issue.get("title") or "").strip() or "(no title)"
        action = payload.get("action") or "?"
        num = issue.get("number", "")
        return f"issue #{num} {action}: {title} ({repo})"

    if et == "CreateEvent":
        ref = payload.get("ref") or ""
        desc = payload.get("description") or ""
        rt = payload.get("ref_type") or "ref"
        extra = f" {desc}" if desc else ""
        return f"created {rt} {ref} in {repo}{extra}"

    if et == "DeleteEvent":
        ref = payload.get("ref") or ""
        return f"deleted {payload.get('ref_type', 'ref')} {ref} in {repo}"

    if et == "ReleaseEvent":
        rel = payload.get("release") or {}
        tag = rel.get("tag_name") or rel.get("name") or "release"
        return f"release {tag} ({repo})"

    if et == "ForkEvent":
        fork = (payload.get("forkee") or {}).get("full_name") or "fork"
        return f"forked {repo} → {fork}"

    if et == "WatchEvent":
        return f"starred {repo}"

    return f"{et} ({repo})"


def collect_public_events(
    profiles: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    *,
    username: str,
    token: Optional[str],
    classify_project: Callable[..., str],
    make_event: Callable[..., Dict[str, Any]],
    api_base: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch `/users/{username}/events/public` (newest first; GitHub retains ~300 recent events).

    Events outside the API window will not appear — sparse for old ranges.
    """
    if not username:
        return []

    base = (api_base or resolve_github_api_base()).rstrip("/")
    if token and not base.lower().startswith("https://"):
        raise ValueError(
            "GitHub API base URL must use HTTPS to prevent token leakage over unencrypted HTTP"
        )

    results: List[Dict[str, Any]] = []
    # Normalize bounds to aware UTC for comparison
    if dt_from.tzinfo is None:
        dt_from = dt_from.replace(tzinfo=timezone.utc)
    if dt_to.tzinfo is None:
        dt_to = dt_to.replace(tzinfo=timezone.utc)
    dt_from_utc = dt_from.astimezone(timezone.utc)
    dt_to_utc = dt_to.astimezone(timezone.utc)

    for page in range(1, MAX_PAGES + 1):
        url = f"{base}/users/{username}/events/public?per_page={PER_PAGE}&page={page}"
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as exc:
            raise RuntimeError(f"GitHub API HTTP {exc.code}: {exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"GitHub API network error: {exc.reason}") from exc

        batch = json.loads(raw)
        if not batch:
            break

        stop_paging = False
        for ev in batch:
            created = ev.get("created_at")
            if not created:
                continue
            ts = _parse_github_ts(created)
            if ts > dt_to_utc:
                continue
            if ts < dt_from_utc:
                stop_paging = True
                break
            detail = _detail_for_event(ev)
            repo = (ev.get("repo") or {}).get("name") or ""
            haystack = f"{repo} {detail}"
            project = classify_project(haystack, profiles)
            row = make_event(GITHUB_SOURCE, ts, detail, project)
            row["_github_user"] = username
            eid = ev.get("id")
            if eid is not None:
                row["_github_event_id"] = str(eid)
            results.append(row)

        if stop_paging:
            break
        if len(batch) < PER_PAGE:
            break

    return results


def merge_github_public_events(
    batches: List[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Drop duplicate public events (same REST `id`) and strip internal keys."""
    seen_ids: set[str] = set()
    seen_noid: set[tuple[str, str]] = set()
    out: List[Dict[str, Any]] = []
    for batch in batches:
        for ev in batch:
            normalized = dict(ev)
            gid = normalized.pop("_github_event_id", None)
            if gid:
                if gid in seen_ids:
                    continue
                seen_ids.add(gid)
            else:
                key = (
                    normalized.get("detail", ""),
                    normalized["timestamp"].astimezone(timezone.utc).isoformat(),
                )
                if key in seen_noid:
                    continue
                seen_noid.add(key)
            out.append(normalized)
    out.sort(key=lambda e: e["timestamp"])
    return out
