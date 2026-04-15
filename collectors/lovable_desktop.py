"""Lovable Desktop app: Chromium history under Application Support (Electron)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List

from collectors.chrome import chrome_time_range, chrome_ts, query_chrome, thin_chrome_visit_rows

SOURCE_NAME = "Lovable (desktop)"
_LOVABLE_URL_RE = re.compile(
    rb"https://[a-z0-9.-]*(?:lovable\.dev|lovable\.app|lovableproject\.com)[^\s\x00\"']*",
    re.IGNORECASE,
)


def lovable_desktop_root(home: Path) -> Path:
    return home / "Library" / "Application Support" / "lovable-desktop"


def lovable_desktop_history_candidates(home: Path) -> List[Path]:
    """Return History database paths (Chromium/Electron), newest installs may create none until first navigation."""
    root = lovable_desktop_root(home)
    if not root.is_dir():
        return []
    out: list[Path] = []
    seen: set[str] = set()
    for path in root.rglob("History"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size < 1:
                continue
        except OSError:
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return sorted(out, key=lambda p: str(p).lower())


def lovable_desktop_has_storage_signals(home: Path) -> bool:
    return bool(_storage_signal_files(home))


def collect_lovable_desktop(
    profiles,
    dt_from,
    dt_to,
    collapse_minutes,
    home,
    epoch_delta_us,
    classify_project: Callable,
    make_event: Callable,
):
    """All visits in the Lovable app Chromium History for the date range (app-local DB — not keyword-filtered).

    Project assignment uses the same classify rules as other sources (URL + title vs match_terms).
    """
    paths = lovable_desktop_history_candidates(home)
    if not paths:
        return _collect_lovable_desktop_from_storage(
            profiles, dt_from, dt_to, home, classify_project, make_event
        )

    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    where_clause = "1=1"
    clause_params: tuple = ()

    rows: list = []
    for history_path in paths:
        rows.extend(query_chrome(history_path, where_clause, dt_from_cu, dt_to_cu, clause_params))
    rows.sort(key=lambda r: r[0])
    rows = thin_chrome_visit_rows(rows, collapse_minutes, epoch_delta_us)

    results = []
    for visit_time_cu, url, title in rows:
        ts = chrome_ts(visit_time_cu, epoch_delta_us)
        detail = (title or url)[:70]
        project = classify_project(f"{url} {title}", profiles)
        results.append(make_event(SOURCE_NAME, ts, detail, project))
    return results


def _storage_signal_files(home: Path) -> List[Path]:
    root = lovable_desktop_root(home)
    candidates = [
        root / "Local Storage" / "leveldb",
        root / "Session Storage",
        root / "IndexedDB",
    ]
    out: list[Path] = []
    for base in candidates:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".log", ".ldb"} and "MANIFEST" not in path.name:
                continue
            out.append(path)
    return out


def _extract_lovable_urls(raw: bytes) -> List[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for m in _LOVABLE_URL_RE.finditer(raw):
        url = m.group(0).decode("utf-8", "ignore")
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url[:220])
    return urls


def _collect_lovable_desktop_from_storage(
    profiles, dt_from, dt_to, home, classify_project: Callable, make_event: Callable
):
    """Fallback when Chromium History is absent: derive Lovable activity signals from local/session storage blobs."""
    files = _storage_signal_files(home)
    results = []
    for path in files:
        try:
            ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if not (dt_from <= ts <= dt_to):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        urls = _extract_lovable_urls(raw)
        for url in urls[:20]:
            project = classify_project(url, profiles)
            detail = f"storage signal — {url[:60]}"
            results.append(make_event(SOURCE_NAME, ts, detail, project))
    return results
