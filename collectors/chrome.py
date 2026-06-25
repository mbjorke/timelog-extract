from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict
from urllib.parse import urlparse

from collectors.ai_logs import _anchors


def split_chrome_tab_title(title: str, *, url: str = "") -> tuple[str | None, str]:
    """Split GitHub tab titles: ``Pull requests · owner/repo``."""
    text = (title or "").strip()
    if not text:
        return None, ""
    # Match the real host, not a substring: github.com.evil.com / notgithub.com
    # contain "github.com" but are not GitHub.
    host = (urlparse(url or "").hostname or "").lower()
    if host != "github.com" and not host.endswith(".github.com"):
        return None, text
    if " · " in text:
        lead, tail = text.split(" · ", 1)
        lead, tail = lead.strip(), tail.strip()
        if lead and tail:
            return lead, tail
    return None, text


def _like_escape(value: str) -> str:
    """Escape SQLite LIKE wildcard characters so values match literally.

    Uses backslash as the escape character; callers must append ESCAPE '\\\\' to
    the predicate string.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def chrome_history_path(home):
    return home / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"


def chrome_history_paths(home: Path):
    """Return ordered Chrome History DB paths across supported local profiles."""
    root = home / "Library" / "Application Support" / "Google" / "Chrome"
    if not root.exists():
        return []
    candidates = []
    default_history = root / "Default" / "History"
    if default_history.exists():
        candidates.append(default_history)
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if not (name.startswith("Profile ") or name == "Guest Profile"):
            continue
        history = child / "History"
        if history.exists():
            candidates.append(history)
    return candidates


def query_chrome(history_path, where_clause, dt_from_cu, dt_to_cu, params=()):
    """Run a constrained Chrome history query against a copied SQLite DB.

    Keep `where_clause` sourced from internal fixed templates only. This helper
    intentionally allows SQL snippets for composability; callers must not pass
    user-controlled raw SQL into `where_clause`.
    """
    if not history_path.exists():
        return []

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    rows = []
    try:
        shutil.copy2(history_path, tmp.name)
        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT v.visit_time, u.url, u.title
            FROM visits v
            JOIN urls u ON v.url = u.id
            WHERE v.visit_time BETWEEN ? AND ?
              AND ({where_clause})
            ORDER BY v.visit_time
            """,
            (dt_from_cu, dt_to_cu, *params),
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception as exc:
        print(f"  [Warning] Chrome history: {exc}")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return rows


def query_chrome_across_profiles(home, where_clause, dt_from_cu, dt_to_cu, params=()):
    rows = []
    for history_path in chrome_history_paths(home):
        rows.extend(query_chrome(history_path, where_clause, dt_from_cu, dt_to_cu, params))
    rows.sort(key=lambda row: row[0])
    return rows


def chrome_time_range(dt_from, dt_to, epoch_delta_us):
    return (
        int(dt_from.astimezone(timezone.utc).timestamp() * 1_000_000) + epoch_delta_us,
        int(dt_to.astimezone(timezone.utc).timestamp() * 1_000_000) + epoch_delta_us,
    )


def chrome_ts(visit_time_cu, epoch_delta_us):
    return datetime.fromtimestamp(
        (visit_time_cu - epoch_delta_us) / 1_000_000, tz=timezone.utc
    )


# Tracked web collectors dedupe by UTC calendar day when collapse is enabled.
WEB_VISIT_COLLAPSE_MINUTES = 24 * 60


def web_visit_collapse_minutes(chrome_collapse_minutes: int) -> int:
    """Tracked web URL collectors always use calendar-day dedupe (non-zero sentinel)."""
    _ = chrome_collapse_minutes
    return WEB_VISIT_COLLAPSE_MINUTES


def normalize_chrome_url(url):
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        path = parsed.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        return f"{parsed.netloc.lower()}{path.lower()}"
    except Exception:
        return (url or "")[:200].lower()


def thin_chrome_visit_rows(rows, collapse_minutes, epoch_delta_us):
    if collapse_minutes <= 0 or not rows:
        return rows
    window_s = collapse_minutes * 60
    out = []
    last_emit_ts_by_norm = {}
    for visit_time_cu, url, title in rows:
        ts = chrome_ts(visit_time_cu, epoch_delta_us)
        norm = normalize_chrome_url(url)
        if not norm:
            out.append((visit_time_cu, url, title))
            continue
        prev = last_emit_ts_by_norm.get(norm)
        if prev is not None and (ts - prev).total_seconds() < window_s:
            continue
        last_emit_ts_by_norm[norm] = ts
        out.append((visit_time_cu, url, title))
    return out


def thin_chrome_visit_rows_by_day(rows, epoch_delta_us):
    """Keep the first visit per normalized URL per UTC calendar day."""
    if not rows:
        return rows
    out = []
    seen = set()
    for visit_time_cu, url, title in rows:
        norm = normalize_chrome_url(url)
        if not norm:
            out.append((visit_time_cu, url, title))
            continue
        day_key = chrome_ts(visit_time_cu, epoch_delta_us).date()
        key = (norm, day_key)
        if key in seen:
            continue
        seen.add(key)
        out.append((visit_time_cu, url, title))
    return out


def dedupe_web_visit_rows(rows, collapse_minutes, epoch_delta_us):
    """Collapse tracked web visits to one event per normalized URL per UTC calendar day."""
    if collapse_minutes <= 0 or not rows:
        return rows
    return thin_chrome_visit_rows_by_day(rows, epoch_delta_us)


def collect_claude_ai_urls(
    profiles,
    dt_from,
    dt_to,
    home,
    epoch_delta_us,
    uncategorized,
    make_event: Callable,
    *,
    collapse_minutes: int = WEB_VISIT_COLLAPSE_MINUTES,
):
    url_map: Dict[str, str] = {}
    for profile in profiles:
        for url in profile["tracked_urls"]:
            if "claude.ai" not in str(url).lower():
                continue
            url_map[url] = profile["name"]
    if not url_map:
        return []

    clauses = " OR ".join(["u.url LIKE ? ESCAPE '\\'" for _ in url_map])
    clause_params = tuple(f"%{_like_escape(url)}%" for url in url_map)
    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    rows = query_chrome_across_profiles(home, clauses, dt_from_cu, dt_to_cu, clause_params)
    rows = dedupe_web_visit_rows(rows, collapse_minutes, epoch_delta_us)

    results = []
    for visit_time_cu, url, title in rows:
        ts = chrome_ts(visit_time_cu, epoch_delta_us)
        chat_id = url.split("/chat/")[-1].split("?")[0][:12] if "/chat/" in url else url[-20:]
        project = next(
            (name for tracked_url, name in url_map.items() if tracked_url in url),
            uncategorized,
        )
        detail = f"chat/{chat_id}… — {(title or '')[:40]}"
        results.append(make_event("Claude.ai (web)", ts, detail, project))
    return results


def collect_gemini_web_urls(
    profiles,
    dt_from,
    dt_to,
    home,
    epoch_delta_us,
    uncategorized,
    make_event: Callable,
    *,
    collapse_minutes: int = WEB_VISIT_COLLAPSE_MINUTES,
):
    url_map: Dict[str, str] = {}
    for profile in profiles:
        for url in profile["tracked_urls"]:
            if "gemini.google.com" not in str(url).lower():
                continue
            url_map[url] = profile["name"]
    if not url_map:
        return []

    clauses = " OR ".join(["u.url LIKE ? ESCAPE '\\'" for _ in url_map])
    clause_params = tuple(f"%{_like_escape(url)}%" for url in url_map)
    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    rows = query_chrome_across_profiles(home, clauses, dt_from_cu, dt_to_cu, clause_params)
    rows = dedupe_web_visit_rows(rows, collapse_minutes, epoch_delta_us)

    results = []
    for visit_time_cu, url, title in rows:
        ts = chrome_ts(visit_time_cu, epoch_delta_us)
        match = None
        best_len = -1
        for tracked_url, name in url_map.items():
            if tracked_url in url and len(tracked_url) > best_len:
                match = name
                best_len = len(tracked_url)
        project = match or uncategorized
        chat_id = url.split("/app/")[-1].split("?")[0][:20] if "/app/" in url else url[-24:]
        detail = f"gemini/app/{chat_id}… — {(title or '')[:40]}"
        results.append(make_event("Gemini (web)", ts, detail, project))
    return results


def collect_chrome(
    profiles,
    dt_from,
    dt_to,
    collapse_minutes,
    home,
    epoch_delta_us,
    classify_project: Callable,
    make_event: Callable,
    include_all: bool = False,
    contains_url: str | None = None,
):
    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    if include_all:
        # Avoid double-counting with dedicated Claude.ai / Gemini (web) collectors.
        where_clause = (
            "NOT (LOWER(u.url) LIKE '%claude.ai%') "
            "AND NOT (LOWER(u.url) LIKE '%gemini.google.com%')"
        )
        clause_params = ()
    else:
        all_keywords = sorted(
            {
                kw.lower()
                for profile in profiles
                for kw in (profile["match_terms"] + [profile["name"]])
                if kw
            }
        )
        if not all_keywords:
            return []
        kw_clauses = " OR ".join(
            ["(LOWER(u.url) LIKE ? ESCAPE '\\' OR LOWER(u.title) LIKE ? ESCAPE '\\')" for _ in all_keywords]
        )
        kw_params = tuple(p for kw in all_keywords for p in (f"%{_like_escape(kw)}%", f"%{_like_escape(kw)}%"))
        where_clause = f"({kw_clauses}) AND u.url NOT LIKE ? AND u.url NOT LIKE ?"
        clause_params = (*kw_params, "%claude.ai%", "%gemini.google.com%")
    rows = query_chrome_across_profiles(home, where_clause, dt_from_cu, dt_to_cu, clause_params)
    if include_all and contains_url:
        needle = contains_url.lower()
        rows = [row for row in rows if needle in (row[1] or "").lower()]
    rows = thin_chrome_visit_rows(rows, collapse_minutes, epoch_delta_us)
    results = []
    for visit_time_cu, url, title in rows:
        ts = chrome_ts(visit_time_cu, epoch_delta_us)
        page_label, page_tail = split_chrome_tab_title((title or "").strip(), url=url or "")
        if include_all:
            detail = (f"{page_tail} — {url}".strip(" —") if url else page_tail)[:240]
        else:
            detail = (page_tail or url or "")[:240]
        project = classify_project(f"{url} {title}", profiles)
        anchors = _anchors(label=page_label) if page_label else None
        results.append(make_event("Chrome", ts, detail, project, anchors=anchors))
    return results
