"""Read git commit timestamps from a local repo for the Git-only time estimate."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List


def _git_user_email(repo_path: Path) -> str:
    """Return git user.email configured in repo, or empty string."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path), "config", "user.email"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _iter_commit_timestamps(
    repo_path: Path,
    author_email: str = "",
    since: str = "1970-01-01",
    until: str = "2099-12-31",
) -> Iterator[datetime]:
    """Yield aware datetime for each matching commit in the repo."""
    cmd = ["git", "-C", str(repo_path), "log", "--format=%aI"]
    if author_email:
        cmd += [f"--author={author_email}"]
    cmd += [f"--after={since}", f"--before={until}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            dt = datetime.fromisoformat(line)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            yield dt
        except ValueError:
            continue


def configured_git_repo_paths(profiles: List[Dict[str, Any]]) -> List[Path]:
    paths: list[Path] = []
    for profile in profiles:
        git_repo = profile.get("git_repo")
        if not git_repo:
            continue
        repo_paths = [git_repo] if isinstance(git_repo, str) else list(git_repo)
        for raw in repo_paths:
            paths.append(Path(str(raw)).expanduser())
    return paths


def git_commits_collector_status(
    profiles: List[Dict[str, Any]],
    *,
    local_tz: Any,
    dt_from: datetime,
    dt_to: datetime,
    git_enabled: bool,
    make_event_fn: Any,
    source_name: str,
) -> Dict[str, Any]:
    """collector_status row for Git commits (--git comparison column)."""
    repo_paths = configured_git_repo_paths(profiles)
    if not repo_paths:
        return {
            "enabled": False,
            "reason": "No profile has git_repo configured",
            "events": 0,
        }
    missing = [p for p in repo_paths if not p.exists()]
    if missing:
        return {
            "enabled": False,
            "reason": f"git_repo path not found ({missing[0].name})",
            "events": 0,
        }
    event_count = 0
    for profile in profiles:
        git_repo = profile.get("git_repo")
        if not git_repo:
            continue
        repo_paths_profile = [git_repo] if isinstance(git_repo, str) else list(git_repo)
        for raw in repo_paths_profile:
            repo = Path(str(raw)).expanduser()
            if not repo.exists():
                continue
            events = collect_git_commit_timestamps(
                repo_path=repo,
                local_tz=local_tz,
                make_event_fn=make_event_fn,
                project=str(profile.get("name") or ""),
                source_name=source_name,
                dt_from=dt_from,
                dt_to=dt_to,
            )
            event_count += len(events)
    if not git_enabled:
        return {
            "enabled": False,
            "reason": "Pass --git on report to include Git-only hours column",
            "events": event_count,
        }
    if event_count == 0:
        return {
            "enabled": True,
            "reason": "git_repo configured; no commits in report window",
            "events": 0,
        }
    return {"enabled": True, "reason": "", "events": event_count}


def collect_git_commit_timestamps(
    repo_path: Path,
    local_tz: Any,
    make_event_fn: Any,
    project: str,
    source_name: str,
    *,
    dt_from: datetime,
    dt_to: datetime,
) -> List[Dict[str, Any]]:
    """Return events from git commit timestamps for a single repo in [dt_from, dt_to]."""
    if not repo_path.exists():
        return []
    email = _git_user_email(repo_path)
    since = dt_from.strftime("%Y-%m-%d")
    until = dt_to.strftime("%Y-%m-%d")
    events = []
    for ts in _iter_commit_timestamps(repo_path, author_email=email, since=since, until=until):
        ts_local = ts.astimezone(local_tz)
        if not (dt_from <= ts_local <= dt_to):
            continue
        events.append(make_event_fn(source_name, ts_local, f"git commit ({repo_path.name})", project))
    return events
