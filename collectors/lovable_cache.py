"""Lovable Desktop Chromium cache evidence (GH-145): mtimes + project titles."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import unquote_plus

from collectors.lovable_desktop import (
    SOURCE_NAME,
    _LOVABLE_PROJECT_UUID_RE,
    _format_lovable_event_detail,
    _is_analytics_uuid_context,
    _merge_storage_events,
    _synthetic_lovable_project_url,
    lovable_desktop_root,
)
from core.chromium_cache import codec_available, iter_cache_entries

_PROJECTS_SEARCH_MARKER = "projects/search"
_CACHE_MAX_FILE_BYTES = 5 * 1024 * 1024
_CACHE_MAX_SCAN_BYTES = 50 * 1024 * 1024
_TIBA_RE = re.compile(
    r"projects/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})[^\"']*tiba=([^&\s\"']+)",
    re.IGNORECASE,
)


def lovable_cache_dirs(home: Path) -> list[Path]:
    root = lovable_desktop_root(home)
    return [
        root / "Cache" / "Cache_Data",
        root / "Code Cache" / "js",
    ]


def lovable_desktop_has_cache_signals(home: Path) -> bool:
    for path in lovable_cache_dirs(home):
        if not path.is_dir():
            continue
        try:
            next(path.iterdir())
            return True
        except StopIteration:
            continue
        except OSError:
            continue
    return False


def lovable_cache_status(home: Path) -> tuple[bool, str]:
    """(usable, reason) for ``gittan doctor``."""
    cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
    if not cache_dir.is_dir():
        return False, "No Lovable cache directory yet (open Lovable Desktop once)"
    if not any(cache_dir.glob("*_0")):
        return False, "No cache entries yet"
    if not codec_available()["brotli"]:
        return True, (
            "Cache present; brotli missing — project titles limited "
            "(pip install 'timelog-extract[cache-evidence]')"
        )
    titles = load_lovable_project_titles(home)
    if titles:
        return True, f"Cache readable ({len(titles)} project titles from projects/search)"
    return True, "Cache readable; projects/search title map not cached yet"


def load_lovable_project_titles(home: Path) -> dict[str, str]:
    """UUID → display_name from cached ``projects/search`` responses."""
    cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
    titles: dict[str, str] = {}
    for entry in iter_cache_entries(cache_dir, _PROJECTS_SEARCH_MARKER):
        try:
            data = json.loads(entry.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        projects = data.get("projects") if isinstance(data, dict) else data
        if not isinstance(projects, list):
            continue
        for row in projects:
            if not isinstance(row, dict):
                continue
            uuid = str(row.get("id") or "").strip().lower()
            name = str(row.get("display_name") or "").strip()
            if uuid and name:
                titles[uuid] = name
    return titles


def _tiba_titles_from_bytes(raw: bytes) -> dict[str, str]:
    text = raw.decode("utf-8", "ignore")
    titles: dict[str, str] = {}
    for match in _TIBA_RE.finditer(text):
        uuid = match.group(1).lower()
        title = unquote_plus(match.group(2).replace("+", " ")).strip()
        if title:
            titles[uuid] = title
    return titles


def _extract_cache_uuids(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", "ignore")
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _LOVABLE_PROJECT_UUID_RE.finditer(text):
        uuid = match.group(1).lower()
        if uuid in seen:
            continue
        if _is_analytics_uuid_context(text, match.start(), match.end()):
            continue
        seen.add(uuid)
        ordered.append(uuid)
    return ordered


def collect_lovable_cache_events(
    profiles,
    dt_from,
    dt_to,
    home: Path,
    classify_project: Callable,
    make_event: Callable,
    *,
    collapse_minutes: int = 15,
    title_map: dict[str, str] | None = None,
) -> list:
    """Emit one event per cache file mtime burst that references a project UUID."""
    titles = title_map if title_map is not None else load_lovable_project_titles(home)
    results: list = []
    scanned_bytes = 0
    for cache_dir in lovable_cache_dirs(home):
        if not cache_dir.is_dir():
            continue
        for path in sorted(cache_dir.iterdir()):
            if not path.is_file():
                continue
            if cache_dir.name == "Cache_Data" and not path.name.endswith("_0"):
                continue
            try:
                stat = path.stat()
                size = stat.st_size
                if size > _CACHE_MAX_FILE_BYTES:
                    continue
                ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if not (dt_from <= ts <= dt_to):
                continue
            if scanned_bytes + size > _CACHE_MAX_SCAN_BYTES:
                break
            scanned_bytes += size
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            tiba_titles = _tiba_titles_from_bytes(raw)
            for uuid in _extract_cache_uuids(raw):
                canonical = _synthetic_lovable_project_url(uuid)
                display_title = titles.get(uuid) or tiba_titles.get(uuid, "")
                project = classify_project(f"{canonical} {display_title}", profiles)
                detail = _format_lovable_event_detail(project, canonical, display_title=display_title)
                results.append(make_event(SOURCE_NAME, ts, detail, project))
    merge_seconds = max(60, int(collapse_minutes or 15) * 60)
    return _merge_storage_events(results, merge_seconds=merge_seconds)
