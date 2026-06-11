"""Discover GitHub repositories via authenticated `gh` CLI (private repos, no local clone)."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any

from core.github_slug_match import (
    is_plausible_github_slug,
    profile_match_term_github_slugs,
    split_github_slug,
)
from core.setup_github_env import probe_gh_cli_auth

_GH_TIMEOUT_SECONDS = 30
_GH_LIST_LIMIT = 500
_GH_ROWS_CACHE: dict[tuple[str, ...], list[dict[str, Any]]] = {}


def _normalize_bounds(dt_from: datetime | None, dt_to: datetime | None) -> tuple[datetime | None, datetime | None]:
    if dt_from is None or dt_to is None:
        return None, None
    if dt_from.tzinfo is None:
        dt_from = dt_from.replace(tzinfo=timezone.utc)
    if dt_to.tzinfo is None:
        dt_to = dt_to.replace(tzinfo=timezone.utc)
    return dt_from.astimezone(timezone.utc), dt_to.astimezone(timezone.utc)


def _format_created_at(ts: datetime, local_tz: Any) -> str:
    if local_tz is not None:
        try:
            return ts.astimezone(local_tz).strftime("%Y-%m-%d %H:%M")
        except (OSError, OverflowError, ValueError):
            pass
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _parse_gh_iso_ts(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _run_gh_repo_list(owner: str) -> list[dict[str, Any]]:
    gh_path = shutil.which("gh")
    if not gh_path:
        return []
    cmd = [
        gh_path,
        "repo",
        "list",
        owner,
        "--limit",
        str(_GH_LIST_LIMIT),
        "--json",
        "nameWithOwner,createdAt,pushedAt",
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def github_owners_for_repo_discovery(
    profiles: list[dict],
    extra_slugs: set[str] | None = None,
) -> set[str]:
    """Real GitHub owners from match_terms slugs only — not tracked_urls host noise."""
    owners: set[str] = set()
    for profile in profiles:
        for slug in profile_match_term_github_slugs(profile):
            owner, _repo = split_github_slug(slug)
            if owner and is_plausible_github_slug(slug):
                owners.add(owner)
    for slug in extra_slugs or set():
        owner, _repo = split_github_slug(str(slug))
        if owner and is_plausible_github_slug(str(slug)):
            owners.add(owner)
    return owners


def _allowed_gh_owners(profiles: list[dict], extra_slugs: set[str] | None) -> set[str]:
    gh_cli = probe_gh_cli_auth()
    if not gh_cli.authenticated:
        return set()
    allowed_owners = github_owners_for_repo_discovery(profiles, extra_slugs)
    login = str(gh_cli.login or "").strip().lower()
    if login:
        allowed_owners.add(login)
    return allowed_owners


def _iter_gh_repo_rows(profiles: list[dict], extra_slugs: set[str] | None) -> list[dict[str, Any]]:
    allowed_owners = _allowed_gh_owners(profiles, extra_slugs)
    if not allowed_owners:
        return []
    cache_key = tuple(sorted(allowed_owners))
    cached = _GH_ROWS_CACHE.get(cache_key)
    if cached is not None:
        return cached
    seen_slugs: set[str] = set()
    rows: list[dict[str, Any]] = []
    for owner in sorted(allowed_owners):
        for row in _run_gh_repo_list(owner):
            slug = str(row.get("nameWithOwner") or "").strip().lower()
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            slug_owner, _repo = split_github_slug(slug)
            if not slug_owner or slug_owner not in allowed_owners:
                continue
            rows.append(row)
    _GH_ROWS_CACHE[cache_key] = rows
    return rows


def collect_gh_repo_list_data(
    dt_from: datetime | None,
    dt_to: datetime | None,
    *,
    profiles: list[dict],
    extra_slugs: set[str] | None = None,
    local_tz: Any = None,
) -> tuple[dict[str, str], dict[str, int]]:
    """
    One ``gh repo list`` pass per known owner.

    Returns:
        created_in_window: slug -> formatted created_at (report window only)
        pushed_epochs: slug -> last pushed epoch from GitHub (all listed repos)
    """
    dt_from_utc, dt_to_utc = _normalize_bounds(dt_from, dt_to)
    created_in_window: dict[str, str] = {}
    pushed_epochs: dict[str, int] = {}
    if dt_from_utc is None or dt_to_utc is None:
        return created_in_window, pushed_epochs

    for row in _iter_gh_repo_rows(profiles, extra_slugs):
        slug = str(row.get("nameWithOwner") or "").strip().lower()
        created = _parse_gh_iso_ts(str(row.get("createdAt") or ""))
        if created is not None and dt_from_utc <= created <= dt_to_utc:
            created_in_window[slug] = _format_created_at(created, local_tz)
        pushed = _parse_gh_iso_ts(str(row.get("pushedAt") or ""))
        if pushed is not None:
            pushed_epochs[slug] = int(pushed.timestamp())
    return created_in_window, pushed_epochs


def collect_gh_repos_created_in_window(
    dt_from: datetime | None,
    dt_to: datetime | None,
    *,
    profiles: list[dict],
    extra_slugs: set[str] | None = None,
    local_tz: Any = None,
) -> dict[str, str]:
    """
    Return ``owner/repo`` -> formatted ``created_at`` for repos created in the report window.

    Uses ``gh repo list <owner>`` per known GitHub owner (config + authenticated login).
    Requires ``gh auth login``; does not use ``GITHUB_TOKEN`` env directly.
    """
    created, _pushed = collect_gh_repo_list_data(
        dt_from,
        dt_to,
        profiles=profiles,
        extra_slugs=extra_slugs,
        local_tz=local_tz,
    )
    return created
