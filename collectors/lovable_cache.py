"""Lovable Desktop Chromium cache evidence (GH-145): mtimes + project titles."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import unquote_plus

from collectors.lovable_desktop import (
    _LOVABLE_PROJECT_UUID_RE,
    SOURCE_NAME,
    _canonicalize_lovable_storage_url,
    _extract_lovable_urls,
    _filter_lovable_storage_urls,
    _format_lovable_event_detail,
    _is_analytics_uuid_context,
    _lovable_project_uuid_key,
    _synthetic_lovable_project_url,
    _trim_lovable_url_blob_suffix,
    lovable_desktop_root,
)
from collectors.lovable_merge import _merge_storage_events, is_plausible_lovable_project_uuid
from core.chromium_cache import CODEC_REINSTALL_HINT, codec_available, iter_cache_entries

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
            f"Cache present; brotli missing — project titles limited ({CODEC_REINSTALL_HINT})"
        )
    titles = load_lovable_project_titles(home)
    if titles:
        return True, f"Cache readable ({len(titles)} project titles from projects/search)"
    return True, "Cache readable; projects/search title map not cached yet"


def load_lovable_project_titles(home: Path, *, raw_cache: dict | None = None) -> dict[str, str]:
    """UUID → display_name from cached ``projects/search`` responses.

    ``raw_cache``, when given, is shared with ``collect_lovable_cache_events``
    so the same ``Cache_Data`` files are read from disk once, not twice, when
    both the title map and the event scan run for one report (GH perf pass).
    """
    cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
    titles: dict[str, str] = {}
    for entry in iter_cache_entries(cache_dir, _PROJECTS_SEARCH_MARKER, raw_cache=raw_cache):
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
    """Legacy bare-UUID scan (tests / debug). Prefer ``_project_uuids_from_cache_activity``."""
    text = raw.decode("utf-8", "ignore")
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _LOVABLE_PROJECT_UUID_RE.finditer(text):
        uuid = match.group(1).lower()
        if uuid in seen:
            continue
        if not is_plausible_lovable_project_uuid(uuid):
            continue
        if _is_analytics_uuid_context(text, match.start(), match.end()):
            continue
        seen.add(uuid)
        ordered.append(uuid)
    return ordered


def _project_uuids_from_cache_activity(
    raw: bytes,
    *,
    tiba_titles: dict[str, str] | None = None,
) -> list[str]:
    """UUIDs from project hosts / ``/projects/<uuid>`` / tiba= — not bare binary tokens."""
    if _PROJECTS_SEARCH_MARKER.encode("ascii") in raw[: min(len(raw), 65_536)]:
        # projects/search bodies feed the title map only; do not emit one row per catalog id.
        return []
    seen: set[str] = set()
    ordered: list[str] = []

    def _admit(uuid: str) -> None:
        if not uuid or uuid in seen or not is_plausible_lovable_project_uuid(uuid):
            return
        seen.add(uuid)
        ordered.append(uuid)

    urls = _filter_lovable_storage_urls(
        _extract_lovable_urls(raw),
        lovable_noise_profile="balanced",
    )
    for url in urls:
        trimmed = _canonicalize_lovable_storage_url(_trim_lovable_url_blob_suffix(url))
        _admit(_lovable_project_uuid_key(trimmed))
        for match in _LOVABLE_PROJECT_UUID_RE.finditer(trimmed):
            # lovable.dev/projects/<uuid> activity URLs (no project-host subdomain).
            if "/projects/" in trimmed.lower():
                _admit(match.group(1).lower())
    titles = tiba_titles if tiba_titles is not None else _tiba_titles_from_bytes(raw)
    for uuid in titles:
        _admit(uuid)
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
    raw_cache: dict | None = None,
) -> list:
    """Emit one event per cache file mtime burst that references a project UUID.

    ``raw_cache``, when given, is checked before reading a file from disk (and
    populated as a side effect) — shared with ``load_lovable_project_titles``
    so a file already read for the title map is not read again here.
    """
    titles = (
        title_map if title_map is not None else load_lovable_project_titles(home, raw_cache=raw_cache)
    )
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
            if raw_cache is not None and path in raw_cache:
                raw = raw_cache[path]
            else:
                try:
                    raw = path.read_bytes()
                except OSError:
                    continue
                if raw_cache is not None:
                    raw_cache[path] = raw
            tiba_titles = _tiba_titles_from_bytes(raw)
            for uuid in _project_uuids_from_cache_activity(raw, tiba_titles=tiba_titles):
                canonical = _synthetic_lovable_project_url(uuid)
                display_title = titles.get(uuid) or tiba_titles.get(uuid, "")
                project = classify_project(f"{canonical} {display_title}", profiles)
                detail = _format_lovable_event_detail(project, canonical, display_title=display_title)
                results.append(make_event(SOURCE_NAME, ts, detail, project))
    merge_seconds = max(60, int(collapse_minutes or 15) * 60)
    return _merge_storage_events(results, merge_seconds=merge_seconds)
