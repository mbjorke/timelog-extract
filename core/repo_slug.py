"""Worktree-invariant project attribution key: the git remote slug.

Git worktrees share the main clone's remote config, so ``owner/repo`` resolved
from the ``origin`` remote is identical across every worktree of a project —
unlike the per-worktree directory leaf (``confident-hopper-fe58c2``), which is
indistinguishable from a real project name at the leaf level. Spec:
``docs/task-prompts/repo-slug-project-attribution.md``.

No network calls: the slug comes from the local git config only.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from core.git_project_bootstrap import _parse_remote


def _is_local_path_remote(url: str) -> bool:
    """True when the "remote" is really a filesystem path.

    A clone of a clone, or a repository with no remote at all, can leave origin
    pointing at a directory. ``_parse_remote`` falls back to the last two path
    segments for self-hosted forges, which is right there and wrong here: it
    turns ``/Users/me/Work/acme-client`` into ``work/acme-client``, an identity
    that was never published, can collide with a real remote of the same name,
    and lifts a directory name — sometimes a customer's — into a project row.
    """
    text = url.strip()
    if not text:
        return False
    # Every spelling of the file scheme, not just the three-slash one: `file:/`
    # and `FILE:///` are the same local path, and either would otherwise reach
    # the path-segment fallback and surface a directory name as an identity.
    if text.lower().startswith("file:"):
        return True
    if text.startswith(("/", "~", ".")):
        return True
    # A published remote names a host, via a scheme or scp-style `host:path`.
    # Without one this is a relative path — `work/clone` from `git clone
    # ../work/clone` — and it is shaped exactly like `owner/repo`, so nothing
    # downstream can tell the two apart. Requiring a host is the only check
    # that can: identity has to come from something that was published.
    if "://" not in text:
        host, sep, path = text.partition(":")
        if not (sep and host and path):
            return True
    # scp-style ``host:owner/repo`` has a host before the colon; a Windows path
    # (``C:\src\repo``) has a single drive letter.
    return len(text) > 1 and text[1] == ":" and text[0].isalpha()


def _strip_scp_host(url: str) -> str:
    """Drop the ``[user@]host:`` prefix from an scp-style remote.

    ``_parse_remote`` special-cases github.com and otherwise takes the last two
    path segments, so ``git@gitlab.com:team/tool`` yields an owner of
    ``git@gitlab.com:team``. Harmless where the result is only a search term;
    not harmless here, where it would become the visible name of a project row.
    """
    text = url.strip()
    if "://" in text:
        return text
    host, sep, path = text.partition(":")
    if sep and path and "/" in path and "/" not in host:
        return path
    return text


def slug_from_remote_url(url) -> str:
    """``owner/repo`` (lowercase) from an https/ssh remote URL, or ``""``.

    A local filesystem path is not a remote and yields ``""``: identity must
    come from something that was actually published.
    """
    text = str(url or "")
    if _is_local_path_remote(text):
        return ""
    owner, repo = _parse_remote(_strip_scp_host(text))
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


def _multi_root_folders(config_path: str) -> list[str]:
    """Folder paths declared inside a ``.code-workspace`` multi-root config.

    VS Code records a multi-root workspace as the path of the ``.code-workspace``
    file, not as the folders it contains. Without expanding it, every folder in
    a multi-root setup fails containment and its activity is silently dropped.
    Relative ``path`` entries resolve against the config file's own directory.
    """
    import json

    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    base = Path(config_path).parent
    folders = []
    for entry in data.get("folders") or ():
        raw = (entry or {}).get("path") if isinstance(entry, dict) else None
        if not raw:
            continue
        candidate = Path(str(raw)).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        # Resolve ".." segments without requiring the path to exist on disk.
        folders.append(str(Path(os.path.normpath(str(candidate)))))
    return folders


def workspace_roots(paths) -> tuple[str, ...]:
    """Normalize opened-workspace folder paths into a lookup for `workspace_root_for`.

    A ``.code-workspace`` entry is replaced by the folders it declares: the file
    itself is not a directory, so containment against it never matches.
    """
    roots: set[str] = set()
    for raw in paths or ():
        text = str(raw or "").rstrip("/")
        if not text:
            continue
        if text.endswith(".code-workspace"):
            roots.update(f.rstrip("/") for f in _multi_root_folders(text) if f)
            continue
        roots.add(text)
    return tuple(sorted(r for r in roots if r))


def workspace_root_for(path, roots: tuple[str, ...]) -> str | None:
    """The opened workspace a scraped log-line path belongs to, or ``None``.

    IDE logs mention paths for many reasons: a file a watcher touched, an
    extension's storage, a crash dump, a directory some harness writes session
    data into. Mentioning a path is not evidence that work happened in it, so a
    scraped path only counts when an opened workspace independently vouches for
    it — it is a workspace root, or sits inside one (GH-529).

    Returns the **root**, not the scraped path, so a nested file attributes to
    the project rather than to whatever directory it happens to sit in. The
    longest matching root wins, which keeps a workspace nested inside another
    attributed to itself.
    """
    norm = str(path or "").rstrip("/")
    if not norm:
        return None
    best = None
    for root in roots:
        if norm == root or norm.startswith(root + "/"):
            if best is None or len(root) > len(best):
                best = root
    return best


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
