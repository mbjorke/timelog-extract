"""Lovable Desktop app: Chromium history under Application Support (Electron)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List
from urllib.parse import urlparse

from collectors.chrome import chrome_time_range, chrome_ts, query_chrome, thin_chrome_visit_rows
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE

SOURCE_NAME = "Lovable (desktop)"
_URL_RE = re.compile(rb"https://[^\s\x00\"']+", re.IGNORECASE)
_LOVABLE_PROJECT_UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
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
    lovable_noise_profile: str = DEFAULT_LOVABLE_NOISE_PROFILE,
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
            collapse_minutes=collapse_minutes,
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
            collapse_minutes=collapse_minutes,
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
    markers = ("lovable.dev", "lovable.app", "lovableproject", ".lovable")
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


def _trim_lovable_url_blob_suffix(url: str) -> str:
    """Drop LevelDB / Session Storage junk appended after the URL token."""
    clean = "".join(ch for ch in (url or "") if ord(ch) >= 32).strip()
    if "^" in clean:
        clean = clean.split("^", 1)[0].rstrip(".,;)")
    return clean


def _lovable_project_uuid_key(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    match = _LOVABLE_PROJECT_UUID_RE.search(host)
    return match.group(1).lower() if match else ""


def _storage_url_last_offset(raw: bytes, url: str) -> int:
    key = _lovable_project_uuid_key(url) or _trim_lovable_url_blob_suffix(url)[:48]
    if not key:
        return -1
    return raw.rfind(key.encode("ascii", "ignore"))


def _storage_tail_min_offset(raw: bytes, *, tail_bytes: int = 768) -> int:
    """Offsets below this are treated as historical cache, not the latest write."""
    size = len(raw)
    return max(0, size - max(128, int(tail_bytes)))


def _synthetic_lovable_project_url(uuid: str) -> str:
    return f"https://{uuid}.lovableproject.com/"


def _register_storage_uuid_candidate(
    best_by_uuid: dict[str, tuple[int, int, str]],
    *,
    uuid: str,
    offset: int,
    url: str,
) -> None:
    prefer = 2 if ".lovableproject.com" in url.lower() else 1 if ".lovable.app" in url.lower() else 0
    prev = best_by_uuid.get(uuid)
    if prev is None or (offset, prefer) > (prev[0], prev[1]):
        best_by_uuid[uuid] = (offset, prefer, url)


def _known_lovable_project_uuids(profiles) -> set[str]:
    known: set[str] = set()
    for profile in profiles or []:
        for term in list(profile.get("match_terms") or []) + list(profile.get("tracked_urls") or []):
            match = _LOVABLE_PROJECT_UUID_RE.search(str(term))
            if match:
                known.add(match.group(1).lower())
    return known


def _pick_storage_urls_from_blob(
    raw: bytes,
    urls: List[str],
    *,
    limit: int,
    tail_bytes: int = 768,
    profiles=None,
) -> List[str]:
    """Keep project URLs from the tail of a storage blob (latest write), not stale cache rows."""
    if limit <= 0:
        return []
    min_offset = _storage_tail_min_offset(raw, tail_bytes=tail_bytes)
    best_by_uuid: dict[str, tuple[int, int, str]] = {}
    for url in urls:
        trimmed = _canonicalize_lovable_storage_url(_trim_lovable_url_blob_suffix(url))
        if not trimmed or not _is_plausible_lovable_storage_url(trimmed):
            continue
        uuid = _lovable_project_uuid_key(trimmed)
        if not uuid:
            continue
        offset = _storage_url_last_offset(raw, trimmed)
        if offset < min_offset:
            continue
        _register_storage_uuid_candidate(best_by_uuid, uuid=uuid, offset=offset, url=trimmed)
    # LevelDB often stores bare project UUIDs without an https:// prefix.
    for match in _LOVABLE_PROJECT_UUID_RE.finditer(raw.decode("utf-8", "ignore")):
        uuid = match.group(1).lower()
        offset = raw.rfind(uuid.encode("ascii", "ignore"))
        if offset < min_offset:
            continue
        _register_storage_uuid_candidate(
            best_by_uuid,
            uuid=uuid,
            offset=offset,
            url=_synthetic_lovable_project_url(uuid),
        )
    ranked = sorted(best_by_uuid.values(), key=lambda row: (row[0], row[1]), reverse=True)
    picked = [url for _offset, _prefer, url in ranked]
    known = _known_lovable_project_uuids(profiles)
    if known:
        tracked = [url for url in picked if _lovable_project_uuid_key(url) in known]
        if tracked:
            return tracked[:limit]
    return picked[:limit]


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
    clean = _trim_lovable_url_blob_suffix(url)
    clean = "".join(ch for ch in clean if ord(ch) >= 32).strip()
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


def _is_generic_lovable_root_url(url: str) -> bool:
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return False
    if (parsed.scheme or "").lower() != "https":
        return False
    host = (parsed.netloc or "").lower().strip().rstrip(".")
    if host not in {"lovable.dev", "www.lovable.dev"}:
        return False
    return (parsed.path or "") in {"", "/"}


def _filter_lovable_storage_urls(urls: List[str], lovable_noise_profile: str = "normal") -> List[str]:
    profile = (lovable_noise_profile or DEFAULT_LOVABLE_NOISE_PROFILE).strip().lower()
    if profile == "normal":
        return urls
    if profile == "strict":
        return [
            url
            for url in urls
            if _is_plausible_lovable_storage_url(url) and not _is_generic_lovable_root_url(url)
        ]
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
        return [url for url in deduped if not _is_generic_lovable_root_url(url)]
    return urls


def _storage_event_score(event: dict) -> tuple[int, int, datetime]:
    detail = str(event.get("detail") or "")
    url = detail.split("—", 1)[-1].strip() if "—" in detail else detail
    host_score = 2 if ".lovableproject.com" in url.lower() else 1 if ".lovable.app" in url.lower() else 0
    uuid_len = len(_lovable_project_uuid_key(url))
    return (host_score, uuid_len, event["timestamp"])


def _pick_best_storage_event(group: list) -> dict:
    return max(enumerate(group), key=lambda item: (_storage_event_score(item[1]), item[0]))[1]


def _merge_storage_events(events: list, *, merge_seconds: int) -> list:
    """Collapse bursts from many LevelDB files touched in the same Lovable session."""
    if not events or merge_seconds <= 0:
        return events
    sorted_events = sorted(events, key=lambda event: event["timestamp"])
    merged: list[dict] = []
    group = [sorted_events[0]]
    for event in sorted_events[1:]:
        gap = (event["timestamp"] - group[-1]["timestamp"]).total_seconds()
        if gap <= merge_seconds:
            group.append(event)
            continue
        merged.append(_pick_best_storage_event(group))
        group = [event]
    merged.append(_pick_best_storage_event(group))
    return merged


def _collect_lovable_desktop_from_storage(
    profiles,
    dt_from,
    dt_to,
    home,
    classify_project: Callable,
    make_event: Callable,
    collapse_minutes: int = 15,
    lovable_noise_profile: str = DEFAULT_LOVABLE_NOISE_PROFILE,
):
    """Fallback when Chromium History is absent: derive Lovable activity signals from local/session storage blobs."""
    files = _storage_signal_files(home)
    results = []
    profile = (lovable_noise_profile or DEFAULT_LOVABLE_NOISE_PROFILE).strip().lower()
    # One tail signal per file touch (balanced/strict): file mtime is shared by every
    # cached UUID in the blob; emitting several rows mis-attributes stale projects.
    per_file_limit = 3 if profile == "normal" else 1
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
        for url in _pick_storage_urls_from_blob(raw, urls, limit=per_file_limit, profiles=profiles):
            uuid = _lovable_project_uuid_key(url)
            canonical = _synthetic_lovable_project_url(uuid) if uuid else url
            project = classify_project(canonical, profiles)
            detail = f"storage signal — {canonical}"
            results.append(make_event(SOURCE_NAME, ts, detail, project))
    merge_seconds = max(60, int(collapse_minutes or 15) * 60)
    return _merge_storage_events(results, merge_seconds=merge_seconds)
