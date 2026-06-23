"""Shared log collector for VS Code-fork IDEs (Antigravity, Windsurf, ...).

These IDEs share the VS Code layout: an application-support directory with
``User/workspaceStorage/<id>/workspace.json`` folder mappings and a timestamped
``logs/`` tree whose lines look like ``2026-05-28 01:33:34.938 [info] ...``.

Each fork supplies its own base dir(s), source name, noise markers, and the set
of its own internal data dirs to ignore; this module owns the parsing, the
time-window filter, workspace→project attribution, and event construction.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

_TS_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_TS_ISO_BRACKET_PATTERN = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})?\]"
)
_WORKSPACE_ID_PATTERN = re.compile(r"workspaceStorage/([^/\s\"']+)")
# macOS-specific: these forks store log data under ~/Library/Application Support,
# so workspace paths in the logs are always absolute /Users/... paths.
_WORKSPACE_PATH_PATTERN = re.compile(r"(/Users/[^\"'\s]+)")

# Operational noise common to every fork, filtered at every noise profile.
SHARED_BASE_NOISE = (
    "error getting submodules",
    "[error] enoent",
    "[error] enotempty",
    "file not found - git:/",
    "[git][revparse] unable to read file",
    "[git][gethead] failed",
    # Extension lifecycle / IDE plumbing — fires on window open and background
    # updates, never user work intent.
    "installing extension",
    "extension is already requested to install",
    "started downloading extension",
    "extracted extension to",
    "extension installed successfully",
    "uninstalling extension",
    "deleted marked for removal extension",
    "using tsserver from",
    "using askpass script",
    # Config-path polling ("User config path:", "Claude user config path:").
    "user config path:",
    "canvas sdk mirror",
)


def read_ide_version(base_dir: Path) -> Optional[str]:
    """Read the installed IDE version from ``<base_dir>/product.json``.

    Returns ``None`` when the file is missing, unreadable, or has no version field.
    """
    product_json = base_dir / "product.json"
    try:
        data = json.loads(product_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Could not read IDE version from %s: %s", product_json, exc)
        return None
    version = data.get("version")
    if version is None:
        logger.debug("No version field in %s", product_json)
        return None
    text = str(version).strip()
    return text or None


def enrich_ide_collector_versions(
    collector_status: Dict[str, Dict[str, object]],
    home: Path,
) -> None:
    """Attach local install version metadata to IDE collector_status entries."""
    from collectors.antigravity import antigravity_base_dir
    from collectors.cursor import cursor_base_dir
    from collectors.windsurf import windsurf_base_dirs

    ide_base_dirs = {
        "Cursor": [cursor_base_dir(home)],
        "Windsurf": windsurf_base_dirs(home),
        "Antigravity": [antigravity_base_dir(home)],
    }
    for name, base_dirs in ide_base_dirs.items():
        status = collector_status.get(name)
        if status is None:
            continue
        for base_dir in base_dirs:
            version = read_ide_version(base_dir)
            if version:
                status["version"] = version
                break


def parse_fork_log_ts(line: str, local_tz):
    """Parse a leading VS Code-fork log timestamp; default naive ISO to local_tz.

    Handles both ``2026-05-28 01:33:34`` (assumed local) and bracketed ISO
    ``[2026-05-28T01:33:34(.fff)(±hh:mm|Z)]``. A bracket timestamp without an
    offset parses naive, so it is pinned to ``local_tz`` to keep the tz-aware
    window comparison from raising ``TypeError``.
    """
    m = _TS_PATTERN.match(line)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=local_tz)
        except ValueError:
            return None
    m = _TS_ISO_BRACKET_PATTERN.match(line)
    if m:
        iso = (m.group(1) + (m.group(2) or "")).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=local_tz)
        return parsed
    return None


def _is_gittan_sync_artifact(text: str) -> bool:
    """True for local Gittan sync/diagnostic artifact lines (never user work)."""
    if ".gittan" in text and ("timelog_projects.json" in text or "decisions-" in text):
        return any(m in text for m in ("upload", "sync", "error", "enoent", "failed"))
    return False


def make_noise_filter(*, base_extra=(), strict=(), ultra_strict=()):
    """Build a noise predicate from marker tiers keyed by noise profile.

    ``lenient`` filters only the shared base (plus ``base_extra`` and Gittan
    artifacts); ``strict`` adds ``strict``; ``ultra-strict`` adds
    ``ultra_strict`` too.
    """
    base = SHARED_BASE_NOISE + tuple(base_extra)
    strict = tuple(strict)
    ultra_strict = tuple(ultra_strict)

    def _is_noise(line: str, noise_profile: str = "strict") -> bool:
        text = (line or "").lower()
        profile = (noise_profile or "strict").strip().lower()
        markers = list(base)
        if profile in {"strict", "ultra-strict"}:
            markers.extend(strict)
        if profile == "ultra-strict":
            markers.extend(ultra_strict)
        if any(marker in text for marker in markers):
            return True
        return _is_gittan_sync_artifact(text)

    return _is_noise


def load_fork_workspaces(base_dir: Path) -> dict:
    """Map workspaceStorage ids to folder paths for one fork base dir (URIs decoded)."""
    storage_dir = base_dir / "User" / "workspaceStorage"
    workspace_map: dict = {}
    if not storage_dir.exists():
        return workspace_map
    for workspace_json in storage_dir.glob("*/workspace.json"):
        workspace_id = workspace_json.parent.name
        try:
            data = json.loads(workspace_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_uri = data.get("folder") or data.get("workspace")
        if not raw_uri:
            continue
        parsed = urlparse(raw_uri)
        path = unquote(parsed.path) if parsed.scheme == "file" else raw_uri
        workspace_map[workspace_id] = path
    return workspace_map


def collect_fork_logs(
    profiles,
    dt_from,
    dt_to,
    home,
    local_tz,
    classify_project,
    make_event,
    *,
    source_name: str,
    base_dirs: Sequence[Path],
    noise_fn: Callable[[str, str], bool],
    internal_paths: Sequence[str],
    noise_profile: str = "strict",
):
    """Scrape one or more VS Code-fork log trees into project-attributed events.

    Each timestamped, non-noise log line in the ``dt_from``..``dt_to`` window is
    attributed to a project via its workspace folder path — the mapped
    workspaceStorage id when present, else a ``/Users/...`` path that is not one
    of the IDE's own ``internal_paths``.
    """
    internals = tuple(p for p in internal_paths if p)
    # Hidden files/dirs directly under home (~/.zshrc, ~/.codeium, ~/.gittan, …)
    # are shell config, tool caches, or agent stores — never project work.
    home_dot_prefix = str(home).rstrip("/") + "/."

    def _is_internal(path: str) -> bool:
        if not path:
            return False
        if path.startswith(home_dot_prefix):
            return True
        return any(path.startswith(marker) for marker in internals)

    results = []
    for base_dir in base_dirs:
        logs_dir = base_dir / "logs"
        if not logs_dir.exists():
            continue
        workspace_map = load_fork_workspaces(base_dir)
        for log_file in logs_dir.glob("**/*.log"):
            try:
                with open(log_file, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        ts = parse_fork_log_ts(line, local_tz)
                        if not ts or not (dt_from <= ts <= dt_to):
                            continue
                        if noise_fn(line, noise_profile):
                            continue
                        workspace_path = None
                        m_id = _WORKSPACE_ID_PATTERN.search(line)
                        if m_id and workspace_map:
                            workspace_path = workspace_map.get(m_id.group(1))
                        if not workspace_path:
                            m_path = _WORKSPACE_PATH_PATTERN.search(line)
                            if m_path and not _is_internal(m_path.group(1)):
                                workspace_path = m_path.group(1)
                        if not workspace_path:
                            continue
                        project = classify_project(f"{workspace_path} {line}", profiles)
                        leaf = Path(workspace_path).name
                        detail = f"{leaf} — {line.strip()[:90]}"
                        dir_leaf = leaf.strip().lower()
                        results.append(
                            make_event(
                                source_name, ts, detail, project,
                                anchors={"dir": dir_leaf} if dir_leaf else None,
                            )
                        )
            except OSError:
                continue
    return results
