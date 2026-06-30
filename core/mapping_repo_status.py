"""Git-local repo bindings and activity for project mapping review."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.git_activity_discovery import collect_git_command_slug_hits
from core.git_project_bootstrap import (
    build_repo_project_seed,
    discover_local_git_repos,
    iter_workspace_git_repos,
    parse_github_origin,
)


@dataclass(frozen=True)
class SlugGitBinding:
    slug: str
    remote_url: str
    local_path: str
    last_commit_epoch: int
    git_cmd_hits: int
    remote_hits: int = 0
    in_window_epoch: int = 0


def _epoch_in_report_window(epoch: int, dt_from: Any, dt_to: Any) -> int:
    if epoch <= 0 or dt_from is None or dt_to is None:
        return 0

    ts = datetime.fromtimestamp(epoch, tz=timezone.utc)
    start = dt_from
    end = dt_to
    if getattr(start, "tzinfo", None) is None:
        start = start.replace(tzinfo=timezone.utc)
    if getattr(end, "tzinfo", None) is None:
        end = end.replace(tzinfo=timezone.utc)
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    if start_utc <= ts <= end_utc:
        return epoch
    return 0


def binding_activity_epoch(binding: SlugGitBinding | None) -> int:
    if binding is None:
        return 0
    return int(binding.in_window_epoch or binding.last_commit_epoch or 0)


def activity_dot(epoch_ts: int) -> str:
    if epoch_ts <= 0:
        return "[dim]●[/dim]"
    now_epoch = int(datetime.now(tz=timezone.utc).timestamp())
    age_days = (now_epoch - epoch_ts) / 86400
    if age_days <= 30:
        return "[green]●[/green]"
    if age_days <= 90:
        return "[yellow]●[/yellow]"
    return "[red]●[/red]"


def format_tilde_path(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve()
        home = Path.home().resolve()
        if resolved == home:
            return "~"
        rel = resolved.relative_to(home)
        return f"~/{rel.as_posix()}"
    except (OSError, ValueError):
        return str(path)


def _git_last_commit_epoch(repo: Path) -> int:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except OSError:
        return 0
    if result.returncode != 0:
        return 0
    try:
        return int((result.stdout or "").strip() or "0")
    except ValueError:
        return 0


def _git_remote_origin(repo: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _default_scan_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in (
        Path.home() / "Workspace",
        Path.home() / "Code",
        Path.home() / "Projects",
        Path.home() / "Developer",
        Path.cwd(),
    ):
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        roots.append(resolved)
    return roots


def slug_to_remote_url(slug: str) -> str:
    clean = str(slug or "").strip().lower().lstrip("/")
    return f"https://github.com/{clean}"


def git_activity_score(binding: SlugGitBinding | None) -> tuple[int, int]:
    if binding is None:
        return (0, 0)
    return (int(binding.git_cmd_hits), int(binding.last_commit_epoch))


def _slug_activity_rank(slug: str, bindings: dict[str, SlugGitBinding]) -> tuple[int, int, int]:
    """Rank slugs: local Cursor git first, then remote evidence, then recency in window."""
    binding = bindings.get(slug)
    if binding is None:
        return (0, 0, 0)
    has_local = binding_has_local_clone(slug, bindings)
    if has_local and binding.git_cmd_hits > 0:
        tier = 3
    elif has_local:
        tier = 2
    elif binding.remote_hits > 0 or binding.in_window_epoch > 0:
        tier = 1
    else:
        return (0, 0, 0)
    signal = binding.git_cmd_hits if has_local else binding.remote_hits
    return (tier, signal, binding.in_window_epoch)


def pick_active_slug_by_git(
    slugs: set[str],
    bindings: dict[str, SlugGitBinding],
    *,
    canonical: str,
) -> str:
    """Pick the duplicate repo variant you are most likely billing against (local git wins)."""
    candidates = [slug for slug in slugs if slug != canonical]
    if not candidates:
        return canonical
    scored = [(slug, _slug_activity_rank(slug, bindings)) for slug in candidates]
    scored = [(slug, rank) for slug, rank in scored if rank > (0, 0, 0)]
    if not scored:
        return canonical
    return max(scored, key=lambda item: item[1])[0]


def index_local_slug_bindings(
    *,
    cursor_home: Path | None = None,
    dt_from: Any = None,
    dt_to: Any = None,
    local_tz: Any = None,
    scan_roots: list[Path] | None = None,
) -> dict[str, SlugGitBinding]:
    """Map github slugs to local folders, last commit time, and in-window git command hits."""
    git_hits: dict[str, tuple[int, str]] = {}
    if dt_from is not None and dt_to is not None:
        tz = local_tz or getattr(dt_from, "tzinfo", None)
        git_hits = collect_git_command_slug_hits(cursor_home or Path.home(), dt_from, dt_to, tz)

    by_slug: dict[str, SlugGitBinding] = {}
    if scan_roots is None:
        roots = _default_scan_roots()
        repo_paths = iter_workspace_git_repos()
    else:
        roots = [Path(root).expanduser().resolve() for root in scan_roots]
        repo_paths = []
        for root in roots:
            repo_paths.extend(discover_local_git_repos(root, max_depth=4, limit=None))
    for repo in repo_paths:
        origin = _git_remote_origin(repo)
        parsed = parse_github_origin(origin)
        if parsed is None:
            continue
        owner, repo_name = parsed
        slug = f"{owner.strip().lower()}/{repo_name.strip().lower()}"
        hits, _folder = git_hits.get(slug, (0, repo.name))
        commit_epoch = _git_last_commit_epoch(repo)
        candidate = SlugGitBinding(
            slug=slug,
            remote_url=slug_to_remote_url(slug),
            local_path=format_tilde_path(repo),
            last_commit_epoch=commit_epoch,
            git_cmd_hits=int(hits),
        )
        existing = by_slug.get(slug)
        if existing is None or git_activity_score(candidate) > git_activity_score(existing):
            by_slug[slug] = candidate

    for slug, (hits, folder_name) in git_hits.items():
        if slug in by_slug:
            current = by_slug[slug]
            if hits > current.git_cmd_hits:
                by_slug[slug] = SlugGitBinding(
                    slug=slug,
                    remote_url=current.remote_url,
                    local_path=current.local_path,
                    last_commit_epoch=current.last_commit_epoch,
                    git_cmd_hits=int(hits),
                )
            continue
        seed = None
        for root in roots:
            candidate = root / folder_name
            if candidate.is_dir() and (candidate / ".git").exists():
                seed = build_repo_project_seed(candidate)
                break
        local_path = format_tilde_path(root / folder_name) if seed else f"~/{folder_name}"
        by_slug[slug] = SlugGitBinding(
            slug=slug,
            remote_url=slug_to_remote_url(slug),
            local_path=local_path,
            last_commit_epoch=0,
            git_cmd_hits=int(hits),
        )
    return by_slug


def binding_has_local_clone(slug: str, bindings: dict[str, SlugGitBinding]) -> bool:
    binding = bindings.get(str(slug or "").strip().lower())
    if binding is None:
        return False
    return binding.local_path not in {"", "(not found on disk)"}


def slug_has_git_evidence(slug: str, bindings: dict[str, SlugGitBinding]) -> bool:
    binding = bindings.get(str(slug or "").strip().lower())
    if binding is None:
        return False
    if binding.git_cmd_hits > 0 or binding.last_commit_epoch > 0:
        return True
    return binding.local_path not in {"", "(not found on disk)"}


def enrich_bindings_with_remote_activity(
    bindings: dict[str, SlugGitBinding],
    events: list[dict],
    *,
    activity: dict[str, int] | None = None,
    gh_pushed_epochs: dict[str, int] | None = None,
    dt_from: Any = None,
    dt_to: Any = None,
) -> dict[str, SlugGitBinding]:
    """Attach in-window remote timestamps/hits without overwriting local git_cmd_hits."""
    from core.github_slug_activity import collect_slug_last_epoch_from_events

    event_epochs = collect_slug_last_epoch_from_events(events)
    gh_epochs = gh_pushed_epochs or {}
    remote_slugs = set(event_epochs) | set(gh_epochs)
    if activity:
        remote_slugs.update(activity)
    if not remote_slugs:
        return bindings

    out = dict(bindings)
    for slug in remote_slugs:
        remote_hits = int((activity or {}).get(slug, 0))
        in_window = max(
            _epoch_in_report_window(event_epochs.get(slug, 0), dt_from, dt_to),
            _epoch_in_report_window(gh_epochs.get(slug, 0), dt_from, dt_to),
        )
        current = out.get(slug)
        if current is None:
            if in_window <= 0 and remote_hits <= 0:
                continue
            out[slug] = SlugGitBinding(
                slug=slug,
                remote_url=slug_to_remote_url(slug),
                local_path="(not found on disk)",
                last_commit_epoch=0,
                git_cmd_hits=0,
                remote_hits=remote_hits,
                in_window_epoch=in_window,
            )
            continue
        local_in_window = _epoch_in_report_window(current.last_commit_epoch, dt_from, dt_to)
        out[slug] = SlugGitBinding(
            slug=current.slug,
            remote_url=current.remote_url,
            local_path=current.local_path,
            last_commit_epoch=current.last_commit_epoch,
            git_cmd_hits=current.git_cmd_hits,
            remote_hits=max(current.remote_hits, remote_hits),
            in_window_epoch=max(current.in_window_epoch, in_window, local_in_window),
        )
    return out


def binding_for_slug(slug: str, bindings: dict[str, SlugGitBinding]) -> SlugGitBinding:
    clean = str(slug or "").strip().lower()
    found = bindings.get(clean)
    if found is not None:
        return found
    return SlugGitBinding(
        slug=clean,
        remote_url=slug_to_remote_url(clean),
        local_path="(not found on disk)",
        last_commit_epoch=0,
        git_cmd_hits=0,
    )
