"""Lovable Desktop app: Chromium history under Application Support (Electron)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List
from urllib.parse import urlparse

from collectors.chrome import chrome_time_range, chrome_ts, query_chrome, thin_chrome_visit_rows

SOURCE_NAME = "Lovable (desktop)"
_URL_RE = re.compile(rb"https://[^\s\x00\"']+", re.IGNORECASE)


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
    lovable_noise_profile: str = "normal",
):
    """All visits in the Lovable app Chromium History for the date range (app-local DB — not keyword-filtered).

    Project assignment uses the same classify rules as other sources (URL + title vs match_terms).
    """
    paths = lovable_desktop_history_candidates(home)
    if not paths:
        return _collect_lovable_desktop_from_storage(
            profiles,
            dt_from,
            dt_to,
            home,
            classify_project,
            make_event,
            lovable_noise_profile=lovable_noise_profile,
        )

    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    where_clause = "1=1"
    clause_params: tuple = ()

    rows: list = []
    for history_path in paths:
        rows.extend(query_chrome(history_path, where_clause, dt_from_cu, dt_to_cu, clause_params))
    rows.sort(key=lambda r: r[0])
    rows = thin_chrome_visit_rows(rows, collapse_minutes, epoch_delta_us)
    if not rows:
        # Some installs create History files but keep useful activity only in storage blobs.
        # Fall back so source visibility doesn't disappear when History is sparse/empty.
        return _collect_lovable_desktop_from_storage(
            profiles,
            dt_from,
            dt_to,
            home,
            classify_project,
            make_event,
            lovable_noise_profile=lovable_noise_profile,
        )

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
    markers = ("lovable.dev", "lovable.app", "lovableproject", ".lov")
    for m in _URL_RE.finditer(raw):
        url = m.group(0).decode("utf-8", "ignore")
        lowered = url.lower()
        if not any(marker in lowered for marker in markers):
            continue
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url[:220])
    return urls


def _is_plausible_lovable_storage_url(url: str) -> bool:
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return False
    host = (parsed.netloc or "").lower().strip()
    if not host:
        return False
    allowed_hosts = ("lovable.dev", "lovable.app", "lovableproject.com")
    if not any(host == h or host.endswith(f".{h}") for h in allowed_hosts):
        return False
    # Reject non-printable noise fragments that can leak from binary blobs.
    if any(ord(ch) < 32 for ch in url):
        return False
    return True


def _canonicalize_lovable_storage_url(url: str) -> str:
    clean = "".join(ch for ch in (url or "") if ord(ch) >= 32).strip()
    try:
        parsed = urlparse(clean)
    except ValueError:
        return ""
    host = (parsed.netloc or "").lower().strip().rstrip(".")
    path = parsed.path or ""
    allowed_hosts = ("lovable.dev", "lovable.app", "lovableproject.com")
    if not host:
        return clean
    # Recover common truncations from binary blob extraction.
    if host.endswith(".lovableproject"):
        host = f"{host}.com"
    elif host.endswith(".lov"):
        host = f"{host}able.app"
    elif host == "lov":
        host = "lovable.app"
    # If host is just "lovableproject", keep source-specific hint if UUID exists in path.
    if host == "lovableproject":
        host = "lovableproject.com"
    if any(host == h or host.endswith(f".{h}") for h in allowed_hosts):
        # Preserve canonical URL if host is valid after light cleanup.
        rebuilt = clean.replace(parsed.netloc, host, 1)
        return rebuilt
    # Common blob-noise case: garbage appended to lovable.dev host.
    if host.startswith("lovable.dev"):
        return "https://lovable.dev"
    # Salvage cases where host is broken but path still contains explicit lovable domains.
    lowered_path = path.lower()
    if "lovableproject.com" in lowered_path:
        return "https://lovableproject.com"
    if "lovable.app" in lowered_path:
        return "https://lovable.app"
    return clean


def _filter_lovable_storage_urls(urls: List[str], lovable_noise_profile: str = "normal") -> List[str]:
    profile = (lovable_noise_profile or "normal").strip().lower()
    if profile == "normal":
        return urls
    if profile == "strict":
        return [url for url in urls if _is_plausible_lovable_storage_url(url)]
    # balanced: salvage likely valid URLs from noisy blobs, then keep plausible ones.
    if profile == "balanced":
        cleaned = [_canonicalize_lovable_storage_url(url) for url in urls]
        deduped: list[str] = []
        seen: set[str] = set()
        for url in cleaned:
            if not url or url in seen:
                continue
            seen.add(url)
            if _is_plausible_lovable_storage_url(url):
                deduped.append(url)
                continue
            # Keep lightly-noisy but still obviously lovable-related URLs.
            lowered = url.lower()
            if "lovable.dev" in lowered or "lovable.app" in lowered or "lovableproject" in lowered:
                deduped.append(url)
        return deduped
    return urls


def _collect_lovable_desktop_from_storage(
    profiles,
    dt_from,
    dt_to,
    home,
    classify_project: Callable,
    make_event: Callable,
    lovable_noise_profile: str = "normal",
):
    """Fallback when Chromium History is absent: derive Lovable activity signals from local/session storage blobs."""
    files = _storage_signal_files(home)
    results = []
    profile = (lovable_noise_profile or "normal").strip().lower()
    per_file_limit = 20 if profile == "normal" else 8 if profile == "balanced" else 20
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
        urls = _filter_lovable_storage_urls(
            _extract_lovable_urls(raw),
            lovable_noise_profile=lovable_noise_profile,
        )
        for url in urls[:per_file_limit]:
            project = classify_project(url, profiles)
            detail = f"storage signal — {url[:60]}"
            results.append(make_event(SOURCE_NAME, ts, detail, project))
    return results
