"""GitHub public activity via REST API (optional; requires username)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.cli_options import package_version
from core.sources import GITHUB_SOURCE

USER_AGENT = (
    f"timelog-extract/{package_version()} "
    "(+https://github.com/mbjorke/timelog-extract)"
)
PER_PAGE = 100
MAX_PAGES = 10


def resolve_github_username(args: Any) -> str:
    """CLI `--github-user` overrides `GITHUB_USER` / `GITHUB_LOGIN`."""
    explicit = getattr(args, "github_user", None)
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    return (os.environ.get("GITHUB_USER") or os.environ.get("GITHUB_LOGIN") or "").strip()


def github_source_enabled(args: Any) -> tuple[bool, Optional[str]]:
    """Return (enabled, disable_reason)."""
    mode = getattr(args, "github_source", "auto")
    if mode == "off":
        return False, "GitHub source disabled via --github-source off"
    user = resolve_github_username(args)
    if mode == "on" and not user:
        return False, "GitHub on but no username (use --github-user or GITHUB_USER)"
    if mode == "auto" and not user:
        return False, "no GitHub username (set --github-user or GITHUB_USER for this source)"
    if not user:
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
) -> List[Dict[str, Any]]:
    """
    Fetch `/users/{username}/events/public` (newest first; GitHub retains ~300 recent events).

    Events outside the API window will not appear — sparse for old ranges.
    """
    if not username:
        return []

    results: List[Dict[str, Any]] = []
    # Normalize bounds to aware UTC for comparison
    if dt_from.tzinfo is None:
        dt_from = dt_from.replace(tzinfo=timezone.utc)
    if dt_to.tzinfo is None:
        dt_to = dt_to.replace(tzinfo=timezone.utc)
    dt_from_utc = dt_from.astimezone(timezone.utc)
    dt_to_utc = dt_to.astimezone(timezone.utc)

    for page in range(1, MAX_PAGES + 1):
        url = f"https://api.github.com/users/{username}/events/public?per_page={PER_PAGE}&page={page}"
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
            results.append(make_event(GITHUB_SOURCE, ts, detail, project))

        if stop_paging:
            break
        if len(batch) < PER_PAGE:
            break

    return results
