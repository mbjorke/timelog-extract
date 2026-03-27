#!/usr/bin/env python3
"""
timelog_extract.py — Flerprojekts-aggregator för lokala arbetsloggar
====================================================================

Summerar aktivitet per dag från:
  1. Claude Code CLI
  2. Claude Desktop
  3. Claude.ai (via specifika chatt-URL:er i Chrome-historiken)
  4. Chrome (projektmatchning via nyckelord)
  5. Apple Mail (skickade mail matchade mot nyckelord)
  6. Gemini CLI
  7. worklog.txt
  8. Screen Time / KnowledgeC (valfri jämförelse, om databasen finns)

Projekt definieras via en JSON-konfigurationsfil. Om ingen konfig finns används
ett bakåtkompatibelt defaultprojekt baserat på CLI-argumenten.
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email import message_from_binary_file
from email.header import decode_header as email_decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

HOME = Path.home()
SCRIPT_DIR = Path(__file__).parent
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
APPLE_EPOCH = 978307200

# Standardinställningar
DEFAULT_KEYWORDS = "membra,segel,pernilla,snippets,wordpress,ass-membra,elementor,rib"
DEFAULT_PROJECT = "ass-membra"
DEFAULT_CLAUDE_URLS = "https://claude.ai/chat/5032e252-a033-4565-b1a7-c3693f69d7a6"
DEFAULT_EMAIL = "marcus.bjorke@blueberry.ax"
DEFAULT_EXCLUDE = (
    "facebook,instagram,etsy,snack och fika,manage wordpress site in natural language,"
    "youtube,twitter,linkedin"
)
DEFAULT_CONFIG = str(SCRIPT_DIR / "timelog_projects.json")
SCREEN_TIME_DB_CANDIDATES = [
    HOME / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db",
    HOME / "Library" / "Application Support" / "KnowledgeC" / "knowledgeC.db",
]
UNCATEGORIZED = "Okategoriserat"

SOURCE_ORDER = [
    "Claude Code CLI",
    "Claude Desktop",
    "Cursor",
    "Gemini CLI",
    "Claude.ai (webb)",
    "worklog.txt",
    "Apple Mail",
    "Chrome",
]

AI_SOURCES = {
    "Claude Code CLI",
    "Claude Desktop",
    "Gemini CLI",
    "Claude.ai (webb)",
    "worklog.txt",
}


def parse_args():
    p = argparse.ArgumentParser(
        description="Aggregera arbetstid från flera lokala källor och flera projekt"
    )
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                   help="Startdatum i lokal tid (default: 30 dagar sedan)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                   help="Slutdatum i lokal tid (default: idag)")
    p.add_argument("--projects-config", default=DEFAULT_CONFIG,
                   help=f"JSON-konfig med projektprofiler (default: {DEFAULT_CONFIG})")
    p.add_argument("--keywords", default=DEFAULT_KEYWORDS,
                   help="Legacy fallback: kommaseparerade projektnyckelord")
    p.add_argument("--project", default=DEFAULT_PROJECT,
                   help="Legacy fallback: projektnamn för AI-loggar")
    p.add_argument("--claude-urls", default=DEFAULT_CLAUDE_URLS,
                   help="Legacy fallback: kommaseparerade Claude.ai chatt-URL:er")
    p.add_argument("--email", default=DEFAULT_EMAIL,
                   help=f"Legacy fallback: mailadress för skickade mail (default: {DEFAULT_EMAIL})")
    p.add_argument("--min-session", dest="min_session", type=int, default=15,
                   help="Minimitid i minuter per AI-session (default: 15)")
    p.add_argument("--min-session-passive", dest="min_session_passive", type=int, default=5,
                   help="Minimitid i minuter för Chrome/Mail-only sessioner (default: 5)")
    p.add_argument("--gap-minutes", type=int, default=30,
                   help="Max paus inom samma session i minuter (default: 30)")
    p.add_argument("--exclude", default=DEFAULT_EXCLUDE,
                   help="Kommaseparerade ord att filtrera bort")
    p.add_argument("--worklog", default=str(SCRIPT_DIR / "worklog.txt"),
                   help="Sökväg till worklog.txt")
    p.add_argument("--screen-time", choices=["auto", "on", "off"], default="auto",
                   help="Jämför mot Screen Time om möjligt (default: auto)")
    p.add_argument("--include-uncategorized", action="store_true",
                   help="Ta med oklassade händelser i rapporten")
    return p.parse_args()


def as_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def normalize_profile(raw):
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("Varje projektprofil måste ha 'name'")
    keywords = as_list(raw.get("keywords"))
    project_terms = as_list(raw.get("project_terms")) or [name]
    claude_urls = as_list(raw.get("claude_urls"))
    email = str(raw.get("email", "")).strip()
    terms = sorted({t.lower() for t in (keywords + project_terms + [name]) if t})
    return {
        "name": name,
        "keywords": keywords,
        "project_terms": project_terms,
        "claude_urls": claude_urls,
        "email": email,
        "match_terms": terms,
    }


def load_profiles(config_path, args):
    cfg = Path(config_path)
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                raw_profiles = data.get("projects", [])
            elif isinstance(data, list):
                raw_profiles = data
            else:
                raise ValueError("JSON måste vara ett objekt eller en lista")
            profiles = [normalize_profile(p) for p in raw_profiles]
            if profiles:
                return profiles, cfg
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"[Varning] Kunde inte läsa projektkonfig {cfg}: {exc}")

    fallback = normalize_profile({
        "name": args.project,
        "keywords": as_list(args.keywords),
        "project_terms": [args.project],
        "claude_urls": as_list(args.claude_urls),
        "email": args.email,
    })
    return [fallback], None


def get_date_range(date_from, date_to):
    now_local = datetime.now(LOCAL_TZ)
    if date_from:
        start_local = datetime.strptime(date_from, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=LOCAL_TZ
        )
    else:
        start_local = (now_local - timedelta(days=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    if date_to:
        end_local = datetime.strptime(date_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=0, tzinfo=LOCAL_TZ
        )
    else:
        end_local = now_local

    return start_local, end_local


def event_key(event):
    return (
        event["source"],
        event["timestamp"].astimezone(timezone.utc).isoformat(),
        event["detail"],
        event.get("project", UNCATEGORIZED),
    )


def dedupe_events(events):
    unique = {}
    for event in events:
        unique[event_key(event)] = event
    return sorted(unique.values(), key=lambda e: e["timestamp"])


def classify_project(text, profiles, fallback=UNCATEGORIZED):
    haystack = (text or "").lower()
    best_name = fallback
    best_score = 0
    for profile in profiles:
        matched = {term for term in profile["match_terms"] if term and term in haystack}
        score = len(matched)
        if profile["name"].lower() in haystack:
            score += 1
        if score > best_score:
            best_score = score
            best_name = profile["name"]
    return best_name


def make_event(source, ts, detail, project):
    return {
        "source": source,
        "timestamp": ts,
        "detail": detail,
        "project": project or UNCATEGORIZED,
    }


def _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
    results = []
    try:
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_raw = obj.get("timestamp") or obj.get("ts") or obj.get("created_at") or obj.get("time")
                if ts_raw is None:
                    continue
                try:
                    if isinstance(ts_raw, (int, float)):
                        divisor = 1000 if ts_raw > 1e11 else 1
                        ts = datetime.fromtimestamp(ts_raw / divisor, tz=timezone.utc)
                    else:
                        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                except (ValueError, OSError):
                    continue

                if not (dt_from <= ts <= dt_to):
                    continue

                msg = obj.get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            c.get("text", "") for c in content if isinstance(c, dict)
                        )
                    detail = str(content)[:70].replace("\n", " ")
                elif isinstance(msg, str):
                    detail = msg[:70]
                else:
                    detail = str(obj.get("type", ""))[:70]

                results.append((ts, detail or "log", obj))
    except (OSError, PermissionError):
        pass
    return results


def collect_claude_code(profiles, dt_from, dt_to):
    results = []
    projects_dir = HOME / ".claude" / "projects"
    if not projects_dir.exists():
        return results

    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        dir_name = proj_dir.name.lower()
        for jsonl_file in proj_dir.glob("*.jsonl"):
            for ts, detail, obj in _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
                match_text = f"{dir_name} {detail} {obj}"
                project = classify_project(match_text, profiles)
                results.append(make_event("Claude Code CLI", ts, detail, project))
    return results


def collect_claude_desktop(profiles, dt_from, dt_to):
    results = []
    sessions_dir = HOME / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    if not sessions_dir.exists():
        return results

    for jsonl_file in sessions_dir.glob("**/*.jsonl"):
        context = str(jsonl_file).lower()
        for ts, detail, obj in _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
            match_text = f"{context} {detail} {obj}"
            project = classify_project(match_text, profiles)
            results.append(make_event("Claude Desktop", ts, detail, project))
    return results


def _query_chrome(where_clause, dt_from_cu, dt_to_cu):
    history_path = HOME / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
    if not history_path.exists():
        return []

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    rows = []
    try:
        shutil.copy2(history_path, tmp.name)
        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT v.visit_time, u.url, u.title
            FROM visits v
            JOIN urls u ON v.url = u.id
            WHERE v.visit_time BETWEEN ? AND ?
              AND ({where_clause})
            ORDER BY v.visit_time
        """, (dt_from_cu, dt_to_cu))
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


def _chrome_time_range(dt_from, dt_to):
    epoch_delta_us = 11_644_473_600 * 1_000_000
    return (
        int(dt_from.astimezone(timezone.utc).timestamp() * 1_000_000) + epoch_delta_us,
        int(dt_to.astimezone(timezone.utc).timestamp() * 1_000_000) + epoch_delta_us,
    )


def _chrome_ts(visit_time_cu):
    epoch_delta_us = 11_644_473_600 * 1_000_000
    return datetime.fromtimestamp(
        (visit_time_cu - epoch_delta_us) / 1_000_000, tz=timezone.utc
    )


def collect_claude_ai_urls(profiles, dt_from, dt_to):
    url_map = {}
    for profile in profiles:
        for url in profile["claude_urls"]:
            url_map[url] = profile["name"]
    if not url_map:
        return []

    clauses = " OR ".join([f"u.url LIKE '%{url}%'" for url in url_map])
    dt_from_cu, dt_to_cu = _chrome_time_range(dt_from, dt_to)
    rows = _query_chrome(clauses, dt_from_cu, dt_to_cu)

    results = []
    for visit_time_cu, url, title in rows:
        ts = _chrome_ts(visit_time_cu)
        chat_id = url.split("/chat/")[-1].split("?")[0][:12] if "/chat/" in url else url[-20:]
        project = next((name for tracked_url, name in url_map.items() if tracked_url in url), UNCATEGORIZED)
        detail = f"chat/{chat_id}… — {(title or '')[:40]}"
        results.append(make_event("Claude.ai (webb)", ts, detail, project))
    return results


def collect_chrome(profiles, dt_from, dt_to):
    all_keywords = sorted({
        kw.lower()
        for profile in profiles
        for kw in (profile["keywords"] + profile["project_terms"] + [profile["name"]])
        if kw
    })
    if not all_keywords:
        return []

    dt_from_cu, dt_to_cu = _chrome_time_range(dt_from, dt_to)
    kw_clauses = " OR ".join(
        [f"(LOWER(u.url) LIKE '%{kw}%' OR LOWER(u.title) LIKE '%{kw}%')" for kw in all_keywords]
    )
    where_clause = f"({kw_clauses}) AND u.url NOT LIKE '%claude.ai%'"

    rows = _query_chrome(where_clause, dt_from_cu, dt_to_cu)
    results = []
    for visit_time_cu, url, title in rows:
        ts = _chrome_ts(visit_time_cu)
        detail = (title or url)[:70]
        project = classify_project(f"{url} {title}", profiles)
        results.append(make_event("Chrome", ts, detail, project))
    return results


def collect_apple_mail(profiles, dt_from, dt_to, default_email=None):
    results = []
    mail_base = HOME / "Library" / "Mail"
    if not mail_base.exists():
        print("  [Varning] ~/Library/Mail hittades inte.")
        return results

    try:
        versions = sorted(mail_base.glob("V[0-9]*"), reverse=True)
    except PermissionError:
        print("  [Varning] Åtkomst nekad till ~/Library/Mail.")
        return results

    if not versions:
        return results
    mail_dir = versions[0]

    sent_patterns = [
        "**/Sent Messages.mbox/Messages/*.emlx",
        "**/Sent.mbox/Messages/*.emlx",
        "**/Skickade meddelanden.mbox/Messages/*.emlx",
        "**/Skickade.mbox/Messages/*.emlx",
        "**/[Ss]ent*/**/*.emlx",
    ]

    emlx_files = []
    try:
        for pat in sent_patterns:
            emlx_files.extend(mail_dir.glob(pat))
    except PermissionError:
        print("  [Varning] Åtkomst nekad till Mail-mappar.")
        return results

    def _decode_header(value):
        if not value:
            return ""
        parts = []
        for raw, charset in email_decode_header(value):
            if isinstance(raw, bytes):
                parts.append(raw.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(raw)
        return "".join(parts)

    senders = {p["email"].lower() for p in profiles if p["email"]}
    if default_email:
        senders.add(default_email.lower())

    for emlx_path in emlx_files:
        try:
            with open(emlx_path, "rb") as f:
                f.readline()
                msg = message_from_binary_file(f)

            date_str = msg.get("Date", "")
            if not date_str:
                continue
            try:
                ts = parsedate_to_datetime(date_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if not (dt_from <= ts <= dt_to):
                continue

            from_addr = (msg.get("From", "") or "").lower()
            if senders and not any(sender in from_addr for sender in senders):
                continue

            to_addr = (msg.get("To", "") or "").lower()
            subject_raw = msg.get("Subject", "") or ""
            subject = _decode_header(subject_raw)
            project = classify_project(f"{to_addr} {subject}", profiles)
            if project == UNCATEGORIZED:
                continue

            detail = f"-> {msg.get('To', '')[:35]}  \"{subject[:45]}\""
            results.append(make_event("Apple Mail", ts, detail, project))
        except PermissionError:
            print("  [Varning] Kan inte läsa enskilt mail — kontrollera Full Disk Access.")
            break
        except Exception:
            continue

    return results


def collect_gemini_cli(profiles, dt_from, dt_to):
    results = []
    base_dir = HOME / ".gemini" / "tmp"
    if not base_dir.exists():
        return results

    for chat_file in base_dir.glob("*/chats/session-*.json"):
        proj_name = chat_file.parent.parent.name.lower()
        try:
            data = json.loads(chat_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for msg in data.get("messages", []):
            ts_raw = msg.get("timestamp")
            if not ts_raw:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if not (dt_from <= ts <= dt_to):
                continue

            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            detail = str(content)[:70].replace("\n", " ")
            role = msg.get("type", "")
            project = classify_project(f"{proj_name} {detail}", profiles)
            results.append(make_event("Gemini CLI", ts, f"[{role}] {detail}" if detail else "Gemini CLI", project))
    return results


def load_cursor_workspaces():
    storage_dir = HOME / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    workspace_map = {}
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


def collect_cursor(profiles, dt_from, dt_to):
    workspace_map = load_cursor_workspaces()
    if not workspace_map:
        return []

    logs_dir = HOME / "Library" / "Application Support" / "Cursor" / "logs"
    if not logs_dir.exists():
        return []

    results = []
    ts_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    workspace_pattern = re.compile(r"workspaceStorage/([0-9a-f]{32})|old id ([0-9a-f]{32})-")

    for log_file in logs_dir.glob("**/*.log"):
        try:
            with open(log_file, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    match = workspace_pattern.search(line)
                    if not match:
                        continue
                    workspace_id = match.group(1) or match.group(2)
                    workspace_path = workspace_map.get(workspace_id)
                    if not workspace_path:
                        continue

                    ts_match = ts_pattern.match(line)
                    if not ts_match:
                        continue
                    try:
                        ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOCAL_TZ)
                    except ValueError:
                        continue
                    if not (dt_from <= ts <= dt_to):
                        continue

                    project = classify_project(f"{workspace_path} {line}", profiles)
                    detail = f"{Path(workspace_path).name} — {line.strip()[:90]}"
                    results.append(make_event("Cursor", ts, detail, project))
        except OSError:
            continue

    return results


def collect_worklog(worklog_path, dt_from, dt_to, profiles):
    results = []
    wl = Path(worklog_path)
    if not wl.exists():
        return results

    ts_pattern = re.compile(r"##\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})")
    try:
        text = wl.read_text(encoding="utf-8")
        for match in ts_pattern.finditer(text):
            try:
                ts = datetime.strptime(
                    f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=LOCAL_TZ)
            except ValueError:
                continue
            if not (dt_from <= ts <= dt_to):
                continue

            start = match.end()
            snippet = text[start:start + 220].strip().split("\n")[0][:120]
            project = classify_project(snippet, profiles)
            results.append(make_event("worklog.txt", ts, snippet or "worklog", project))
    except OSError:
        pass
    return results


def split_duration_by_local_day(start_ts, end_ts):
    current = start_ts.astimezone(LOCAL_TZ)
    end_local = end_ts.astimezone(LOCAL_TZ)
    while current < end_local:
        next_midnight = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        segment_end = min(next_midnight, end_local)
        seconds = max((segment_end - current).total_seconds(), 0)
        if seconds > 0:
            yield current.date().isoformat(), seconds
        current = segment_end


def detect_screen_time_db():
    for path in SCREEN_TIME_DB_CANDIDATES:
        if path.exists():
            return path
    return None


def collect_screen_time(dt_from, dt_to):
    db_path = detect_screen_time_db()
    if not db_path:
        return None, "knowledgeC.db hittades inte"

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    daily_seconds = defaultdict(float)
    try:
        shutil.copy2(db_path, tmp.name)
        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ZSTARTDATE, ZENDDATE, COALESCE(ZVALUESTRING, '')
            FROM ZOBJECT
            WHERE ZSTREAMNAME = '/app/usage'
              AND ZSTARTDATE IS NOT NULL
              AND ZENDDATE IS NOT NULL
              AND ZENDDATE > ZSTARTDATE
            ORDER BY ZSTARTDATE
        """)
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        return None, f"kunde inte läsa Screen Time-databasen: {exc}"
    except PermissionError:
        return None, "ingen åtkomst till knowledgeC.db"
    except Exception as exc:
        return None, f"Screen Time-läsning misslyckades: {exc}"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    for start_raw, end_raw, _bundle_id in rows:
        start_ts = datetime.fromtimestamp(float(start_raw) + APPLE_EPOCH, tz=timezone.utc)
        end_ts = datetime.fromtimestamp(float(end_raw) + APPLE_EPOCH, tz=timezone.utc)
        if end_ts < dt_from or start_ts > dt_to:
            continue
        clipped_start = max(start_ts, dt_from)
        clipped_end = min(end_ts, dt_to)
        for day, seconds in split_duration_by_local_day(clipped_start, clipped_end):
            daily_seconds[day] += seconds

    return daily_seconds, str(db_path)


def group_by_day(events, exclude_keywords=None):
    excl = [k.lower() for k in (exclude_keywords or [])]
    days = {}
    for event in events:
        detail_lower = event.get("detail", "").lower()
        if excl and any(kw in detail_lower for kw in excl):
            continue
        local_ts = event["timestamp"].astimezone(LOCAL_TZ)
        day = local_ts.date().isoformat()
        days.setdefault(day, []).append({**event, "local_ts": local_ts})
    return days


def compute_sessions(entries, gap_minutes=30):
    if not entries:
        return []
    sorted_entries = sorted(entries, key=lambda x: x["local_ts"])
    sessions = []
    s_start = sorted_entries[0]["local_ts"]
    s_end = sorted_entries[0]["local_ts"]
    s_events = [sorted_entries[0]]

    for event in sorted_entries[1:]:
        gap_s = (event["local_ts"] - s_end).total_seconds()
        if gap_s <= gap_minutes * 60:
            s_end = event["local_ts"]
            s_events.append(event)
        else:
            sessions.append((s_start, s_end, s_events))
            s_start = event["local_ts"]
            s_end = event["local_ts"]
            s_events = [event]

    sessions.append((s_start, s_end, s_events))
    return sessions


def session_duration_hours(session_events, start_ts, end_ts, min_session_minutes, min_session_passive_minutes):
    min_h = min_session_minutes / 60
    min_passive_h = min_session_passive_minutes / 60
    sources = {event["source"] for event in session_events}
    minimum = min_h if sources & AI_SOURCES else min_passive_h
    return max((end_ts - start_ts).total_seconds() / 3600, minimum)


def estimate_hours_by_day(days, gap_minutes, min_session_minutes, min_session_passive_minutes):
    per_day = {}
    for day, entries in days.items():
        sessions = compute_sessions(entries, gap_minutes=gap_minutes)
        total_h = sum(
            session_duration_hours(events, start, end, min_session_minutes, min_session_passive_minutes)
            for start, end, events in sessions
        )
        per_day[day] = {"entries": entries, "sessions": sessions, "hours": total_h}
    return per_day


def print_report(overall_days, project_reports, screen_time_days, profiles, args, config_path):
    sep = "─" * 64
    print(f"\n{'═' * 64}")
    print("  TIDLOGGAR — SAMMANSTÄLLNING")
    print(f"{'═' * 64}\n")

    if config_path:
        print(f"Projektkonfig: {config_path}")
    else:
        print("Projektkonfig: legacy fallback från CLI-argument")
    print(f"Lokal tidszon: {LOCAL_TZ}")
    print(f"Projekt: {', '.join(profile['name'] for profile in profiles)}")
    print()

    total_h = 0.0
    for day in sorted(overall_days):
        payload = overall_days[day]
        total_h += payload["hours"]
        entries = sorted(payload["entries"], key=lambda x: x["local_ts"])
        sources = sorted(
            {event["source"] for event in entries},
            key=lambda source: SOURCE_ORDER.index(source) if source in SOURCE_ORDER else 99
        )
        project_names = sorted({event["project"] for event in entries if event["project"] != UNCATEGORIZED})
        print(f"📅  {day}")
        print(f"    Sessioner: {len(payload['sessions'])}  →  estimerat ~{payload['hours']:.1f}h")
        print(f"    Källor:    {', '.join(sources)}")
        print(f"    Projekt:   {', '.join(project_names) if project_names else UNCATEGORIZED}")
        if screen_time_days is not None:
            screen_h = screen_time_days.get(day, 0.0) / 3600
            delta = payload["hours"] - screen_h
            print(f"    Screen Time: ~{screen_h:.1f}h  (delta {delta:+.1f}h)")

        for idx, (start_ts, end_ts, session_events) in enumerate(payload["sessions"], 1):
            dur = session_duration_hours(
                session_events, start_ts, end_ts,
                args.min_session, args.min_session_passive
            )
            session_projects = sorted({event["project"] for event in session_events})
            print(
                f"    [{idx}] {start_ts.strftime('%H:%M')}–{end_ts.strftime('%H:%M')} "
                f"({dur:.1f}h, {len(session_events)} händelser, {', '.join(session_projects)})"
            )
            shown = []
            for event in session_events:
                marker = f"{event['project']} | {event['detail']}"
                if marker in shown:
                    continue
                print(
                    f"        · {event['local_ts'].strftime('%H:%M')}  "
                    f"[{event['source']}] [{event['project']}]  {event['detail']}"
                )
                shown.append(marker)
                if len(shown) >= 5:
                    remaining = len(session_events) - len(shown)
                    if remaining > 0:
                        print(f"          … och {remaining} till")
                    break
        print()

    print(sep)
    print(f"  TOTALT ESTIMERAT:  ~{total_h:.1f}h")
    if screen_time_days is not None:
        screen_total_h = sum(screen_time_days.values()) / 3600
        print(f"  SCREEN TIME TOTALT: ~{screen_total_h:.1f}h")
        print(f"  DELTA:              {total_h - screen_total_h:+.1f}h")
    print(sep)
    print()

    print("Per projekt:")
    for project_name in sorted(project_reports):
        hours = sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
        days = len(project_reports[project_name])
        print(f"  - {project_name}: ~{hours:.1f}h över {days} dagar")
    print()
    print("  OBS: Totalen ovan är den sammanlagda tidslinjen över alla källor.")
    print("  Per projekt räknas på projektmärkta händelser och kan avvika från totalen.")
    print("  Worklog tolkas nu i lokal tid i stället för UTC.")
    if not args.include_uncategorized:
        print("  Oklassade händelser exkluderas från rapporten som standard.")
    if screen_time_days is not None:
        print("  Screen Time kommer från KnowledgeC app-usage och är en jämförelsesignal, inte facit.")
    print()


def main():
    args = parse_args()
    dt_from, dt_to = get_date_range(args.date_from, args.date_to)
    profiles, config_path = load_profiles(args.projects_config, args)

    print(f"\nSöker: {dt_from.date()} → {dt_to.date()}")
    print(f"Lokal tidszon: {LOCAL_TZ}")
    print(f"Projektprofiler: {len(profiles)}")
    print()

    all_events = []

    print("[1/8] Claude Code CLI …")
    cc = collect_claude_code(profiles, dt_from, dt_to)
    print(f"      {len(cc)} händelser\n")
    all_events.extend(cc)

    print("[2/8] Claude Desktop …")
    cd = collect_claude_desktop(profiles, dt_from, dt_to)
    print(f"      {len(cd)} händelser\n")
    all_events.extend(cd)

    print("[3/8] Claude.ai (specifika URL:er) …")
    ca = collect_claude_ai_urls(profiles, dt_from, dt_to)
    print(f"      {len(ca)} besök\n")
    all_events.extend(ca)

    print("[4/8] Chrome …")
    ch = collect_chrome(profiles, dt_from, dt_to)
    print(f"      {len(ch)} besök\n")
    all_events.extend(ch)

    print("[5/9] Gemini CLI …")
    gc = collect_gemini_cli(profiles, dt_from, dt_to)
    print(f"      {len(gc)} händelser\n")
    all_events.extend(gc)

    print("[6/9] Cursor …")
    cu = collect_cursor(profiles, dt_from, dt_to)
    print(f"      {len(cu)} händelser\n")
    all_events.extend(cu)

    print("[7/9] Apple Mail …")
    am = collect_apple_mail(profiles, dt_from, dt_to, default_email=args.email)
    print(f"      {len(am)} mail\n")
    all_events.extend(am)

    print("[8/9] worklog.txt …")
    wl = collect_worklog(args.worklog, dt_from, dt_to, profiles)
    print(f"      {len(wl)} timestamps\n")
    all_events.extend(wl)

    screen_time_days = None
    print("[9/9] Screen Time …")
    if args.screen_time == "off":
        print("      avstängt via --screen-time off\n")
    else:
        screen_time_days, screen_msg = collect_screen_time(dt_from, dt_to)
        if screen_time_days is None:
            if args.screen_time == "on":
                print(f"      kunde inte läsa Screen Time: {screen_msg}\n")
            else:
                print(f"      hoppar över: {screen_msg}\n")
        else:
            print(f"      {len(screen_time_days)} dagar lästa från {screen_msg}\n")

    all_events = dedupe_events(all_events)
    included_events = all_events if args.include_uncategorized else [
        event for event in all_events if event["project"] != UNCATEGORIZED
    ]

    if not included_events:
        print("Inga händelser hittades.")
        return

    exclude = [k.strip() for k in args.exclude.split(",") if k.strip()]
    grouped = group_by_day(included_events, exclude_keywords=exclude)
    overall_days = estimate_hours_by_day(
        grouped,
        gap_minutes=args.gap_minutes,
        min_session_minutes=args.min_session,
        min_session_passive_minutes=args.min_session_passive,
    )

    project_reports = {}
    for project_name in sorted({event["project"] for event in included_events}):
        project_events = [event for event in included_events if event["project"] == project_name]
        project_grouped = group_by_day(project_events, exclude_keywords=exclude)
        project_reports[project_name] = estimate_hours_by_day(
            project_grouped,
            gap_minutes=args.gap_minutes,
            min_session_minutes=args.min_session,
            min_session_passive_minutes=args.min_session_passive,
        )

    print_report(overall_days, project_reports, screen_time_days, profiles, args, config_path)


if __name__ == "__main__":
    main()
