from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from typing import Callable, Dict, List, Sequence, Tuple
from urllib.parse import urlparse


def chrome_history_path(home):
    return home / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"


def query_chrome(history_path, where_clause, dt_from_cu, dt_to_cu):
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
            (dt_from_cu, dt_to_cu),
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception as exc:
        print(f"  [Varning] Chrome history: {exc}")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
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


def collect_claude_ai_urls(
    profiles,
    dt_from,
    dt_to,
    home,
    epoch_delta_us,
    uncategorized,
    make_event: Callable,
):
    url_map: Dict[str, str] = {}
    for profile in profiles:
        for url in profile["tracked_urls"]:
            if "claude.ai" not in str(url).lower():
                continue
            url_map[url] = profile["name"]
    if not url_map:
        return []

    clauses = " OR ".join([f"u.url LIKE '%{url}%'" for url in url_map])
    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    history_path = chrome_history_path(home)
    rows = query_chrome(history_path, clauses, dt_from_cu, dt_to_cu)

    results = []
    for visit_time_cu, url, title in rows:
        ts = chrome_ts(visit_time_cu, epoch_delta_us)
        chat_id = url.split("/chat/")[-1].split("?")[0][:12] if "/chat/" in url else url[-20:]
        project = next(
            (name for tracked_url, name in url_map.items() if tracked_url in url),
            uncategorized,
        )
        detail = f"chat/{chat_id}… — {(title or '')[:40]}"
        results.append(make_event("Claude.ai (webb)", ts, detail, project))
    return results


def collect_gemini_web_urls(
    profiles,
    dt_from,
    dt_to,
    home,
    epoch_delta_us,
    uncategorized,
    make_event: Callable,
):
    url_map: Dict[str, str] = {}
    for profile in profiles:
        for url in profile["tracked_urls"]:
            if "gemini.google.com" not in str(url).lower():
                continue
            url_map[url] = profile["name"]
    if not url_map:
        return []

    clauses = " OR ".join(
        [f"u.url LIKE '%{url.replace(chr(39), chr(39) * 2)}%'" for url in url_map]
    )
    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    history_path = chrome_history_path(home)
    rows = query_chrome(history_path, clauses, dt_from_cu, dt_to_cu)

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
        results.append(make_event("Gemini (webb)", ts, detail, project))
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
):
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

    dt_from_cu, dt_to_cu = chrome_time_range(dt_from, dt_to, epoch_delta_us)
    kw_clauses = " OR ".join(
        [f"(LOWER(u.url) LIKE '%{kw}%' OR LOWER(u.title) LIKE '%{kw}%')" for kw in all_keywords]
    )
    where_clause = (
        f"({kw_clauses}) AND u.url NOT LIKE '%claude.ai%' "
        "AND u.url NOT LIKE '%gemini.google.com%'"
    )
    history_path = chrome_history_path(home)
    rows = query_chrome(history_path, where_clause, dt_from_cu, dt_to_cu)
    rows = thin_chrome_visit_rows(rows, collapse_minutes, epoch_delta_us)
    results = []
    for visit_time_cu, url, title in rows:
        ts = chrome_ts(visit_time_cu, epoch_delta_us)
        detail = (title or url)[:70]
        project = classify_project(f"{url} {title}", profiles)
        results.append(make_event("Chrome", ts, detail, project))
    return results
