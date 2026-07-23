"""Worktree-invariant project attribution key: the git remote slug.

Git worktrees share the main clone's remote config, so ``owner/repo`` resolved
from the ``origin`` remote is identical across every worktree of a project —
unlike the per-worktree directory leaf (``confident-hopper-fe58c2``), which is
indistinguishable from a real project name at the leaf level. Spec:
``docs/task-prompts/repo-slug-project-attribution.md``.

No network calls: the slug comes from the local git config only.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from core.git_project_bootstrap import _parse_remote


def slug_from_remote_url(url) -> str:
    """``owner/repo`` (lowercase) from an https/ssh remote URL, or ``""``."""
    owner, repo = _parse_remote(str(url or ""))
    owner = owner.strip().lower()
    repo = repo.strip().lower()
    if not owner or not repo:
        return ""
    return f"{owner}/{repo}"


@lru_cache(maxsize=1024)
def resolve_path_repo_slug(path_str: str) -> str:
    """Resolve a working-directory path to its remote slug (``""`` if none).

    Works from any git worktree, since worktrees share the main clone's remote
    config. Cached per path so collectors do not shell out once per event.

    A path that no longer exists (a removed worktree) walks up to the nearest
    existing directory: a worktree nested under the project tree
    (``<project>/.claude/worktrees/<gone>``) then still resolves to the
    project's own remote, while a deleted sibling worktree resolves to nothing.
    """
    raw = str(path_str or "").strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    while not path.is_dir():
        parent = path.parent
        if parent == path:
            return ""
        path = parent
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return slug_from_remote_url(completed.stdout)


# Dir leaves that are OS/IDE path artifacts, never real project folders.
# "application" is the classic truncation of macOS "Application Support"
# when a /Users/... extractor stops at whitespace.
_JUNK_DIR_LEAVES = frozenset(
    {
        "application",
        "library",
        "users",
        "home",
    }
)


def path_attribution_anchor(path) -> dict[str, str] | None:
    """Attribution anchor for a working path.

    Prefers the **worktree-invariant repo slug** (``{"repo": "owner/repo"}``) when
    the path is in a git repo, falling back to the directory leaf
    (``{"dir": "<leaf>"}``) for non-git directories. Using the slug means an
    ephemeral worktree leaf (Conductor's invented city names, Claude Code's hex
    suffixes) never becomes the attribution key — map the repo once and every
    worktree of it is covered.
    """
    raw = str(path or "").strip()
    if not raw:
        return None
    # Truncated macOS Application Support path (regex stops at the space).
    if raw.rstrip("/").endswith("/Library/Application"):
        return None
    slug = resolve_path_repo_slug(raw)
    if slug:
        return {"repo": slug}
    leaf = Path(raw).name.strip().lower()
    if not leaf or leaf in _JUNK_DIR_LEAVES:
        return None
    return {"dir": leaf}
