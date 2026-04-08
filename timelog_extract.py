#!/usr/bin/env python3
"""
timelog_extract.py — Flerprojekts-aggregator för lokala arbetsloggar
====================================================================

Summerar aktivitet per dag från:
  1. Claude Code CLI (Claude för Mac, Code Agent — ~/.claude/projects/)
  2. Claude Desktop
  3. Claude.ai (specifika chatt-URL:er i Chrome-historiken)
  4. Google Gemini i webbläsaren (specifika app-URL:er, som claude_urls)
  5. Chrome (projektmatchning via nyckelord)
  6. Gemini CLI (lokala JSON-sessioner under ~/.gemini/tmp)
  7. Cursor (IDE-loggar — workspace-lås, m.m.)
  8. Cursor checkpoints (Cursor-appen → …/cursor-commits/checkpoints)
  9. Codex IDE (OpenAI:s egen app — ~/.codex/session_index.jsonl)
  10. Apple Mail
  11. TIMELOG.md
  12. Screen Time / KnowledgeC (valfri jämförelse)

Projekt definieras via en JSON-konfigurationsfil. Om ingen konfig finns används
ett bakåtkompatibelt defaultprojekt baserat på CLI-argumenten.
"""

import argparse
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
from html import escape as html_escape
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email import message_from_binary_file
from email.header import decode_header as email_decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse
from collectors import chrome as chrome_collector
from collectors import timelog as timelog_collector
from core import domain as core_domain

HOME = Path.home()
SCRIPT_DIR = Path(__file__).parent
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
APPLE_EPOCH = 978307200
CHROME_EPOCH_DELTA_US = 11_644_473_600 * 1_000_000

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


def default_worklog_path() -> Path:
    """Standardfil för timelog i projektet: TIMELOG.md."""
    cwd = Path.cwd() / "TIMELOG.md"
    if cwd.is_file():
        return cwd
    local = SCRIPT_DIR / "TIMELOG.md"
    if local.is_file():
        return local
    return SCRIPT_DIR / "TIMELOG.md"


def resolve_worklog_path(cli_worklog, config_path, workspace_worklog):
    """
    cli_worklog: None om --worklog inte angavs (då används ev. worklog i JSON, sedan default).
    workspace_worklog: valfritt strängvärde från rotobjektet i timelog_projects.json.
    Relativa sökvägar i JSON löses mot konfigfilens katalog.
    """
    if cli_worklog is not None:
        return Path(cli_worklog).expanduser()
    if workspace_worklog:
        p = Path(str(workspace_worklog).strip()).expanduser()
        if not p.is_absolute():
            base = Path(config_path).parent if config_path else SCRIPT_DIR
            p = (base / p).resolve()
        return p
    return default_worklog_path()


SCREEN_TIME_DB_CANDIDATES = [
    HOME / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db",
    HOME / "Library" / "Application Support" / "KnowledgeC" / "knowledgeC.db",
]
CURSOR_CHECKPOINTS_DIR = (
    HOME
    / "Library"
    / "Application Support"
    / "Cursor"
    / "User"
    / "globalStorage"
    / "anysphere.cursor-commits"
    / "checkpoints"
)
CODEX_IDE_DIR = HOME / ".codex"
CODEX_IDE_SESSION_INDEX = CODEX_IDE_DIR / "session_index.jsonl"
UNCATEGORIZED = "Okategoriserat"
# Cursor-appens agent-checkpoints; skild från "Cursor"-loggar och från OpenAI Codex IDE (~/.codex).
CURSOR_CHECKPOINTS_SOURCE = "Cursor checkpoints"
WORKLOG_SOURCE = "TIMELOG.md"

SOURCE_ORDER = [
    "Claude Code CLI",
    "Claude Desktop",
    "Claude.ai (webb)",
    "Gemini (webb)",
    "Cursor",
    CURSOR_CHECKPOINTS_SOURCE,
    "Codex IDE",
    "Gemini CLI",
    WORKLOG_SOURCE,
    "Apple Mail",
    "Chrome",
]

AI_SOURCES = {
    "Claude Code CLI",
    "Claude Desktop",
    "Gemini CLI",
    "Claude.ai (webb)",
    "Gemini (webb)",
    CURSOR_CHECKPOINTS_SOURCE,
    "Codex IDE",
    WORKLOG_SOURCE,
}


@dataclass
class ReportPayload:
    dt_from: datetime
    dt_to: datetime
    profiles: List[Dict[str, Any]]
    config_path: Optional[Path]
    worklog_path: Path
    all_events: List[Dict[str, Any]]
    included_events: List[Dict[str, Any]]
    grouped: Dict[str, Any]
    overall_days: Dict[str, Any]
    project_reports: Dict[str, Any]
    screen_time_days: Optional[Dict[str, float]]
    args: argparse.Namespace


def default_invoice_pdf_path(dt_to):
    stamp = dt_to.astimezone(LOCAL_TZ).date().isoformat()
    return SCRIPT_DIR / "output" / "pdf" / f"timelog-invoice-{stamp}.pdf"


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
    p.add_argument("--gap-minutes", type=int, default=15,
                   help="Luckor kortare än N minuter limmar ihop sessionen (default: 15)")
    p.add_argument("--chrome-collapse-minutes", type=int, default=12,
                   help="Hoppar över upprepade Chrome-besök till samma sida inom N min (0=av; minskar refresh-brus)")
    p.add_argument("--exclude", default=DEFAULT_EXCLUDE,
                   help="Kommaseparerade ord att filtrera bort")
    p.add_argument(
        "--worklog",
        default=None,
        metavar="PATH",
        help="Sökväg till timelogfil (default: TIMELOG.md i projektroten)",
    )
    p.add_argument("--screen-time", choices=["auto", "on", "off"], default="auto",
                   help="Jämför mot Screen Time om möjligt (default: auto)")
    p.add_argument("--include-uncategorized", action="store_true",
                   help="Ta med oklassade händelser i rapporten")
    p.add_argument(
        "--only-project",
        metavar="NAMN",
        default=None,
        help="Visa endast händelser för detta projekt (exakt samma sträng som 'name' i JSON)",
    )
    p.add_argument(
        "--customer",
        metavar="NAMN",
        default=None,
        help="Visa endast händelser för denna kund (matchar 'customer' i JSON, annars projektnamn)",
    )
    p.add_argument(
        "--today",
        action="store_true",
        help="Begränsa till dagens datum i lokal tidszon (--from och --to sätts båda till idag)",
    )
    p.add_argument(
        "--all-events",
        action="store_true",
        help="Skriv ut varje händelse per session (annars max 5 olika rader per session)",
    )
    p.add_argument(
        "--source-summary",
        action="store_true",
        help="Skriv antal händelser per källa efter filter (IDE-loggar vs checkpoints m.m.)",
    )
    p.add_argument(
        "--invoice-pdf",
        action="store_true",
        help="Skapa en fakturavanlig PDF-sammanfattning av timmarna",
    )
    p.add_argument(
        "--invoice-pdf-file",
        default=None,
        help="Valfri filvag for PDF (default: output/pdf/timelog-invoice-<datum>.pdf)",
    )
    p.add_argument(
        "--billable-unit",
        type=float,
        default=0.0,
        metavar="TIMMAR",
        help=(
            "Fakturerbar granularitet (0=av, t.ex. 0.25): råtid summeras per projekt/kund forst, "
            "sedan avrundas slutsumman uppåt till närmaste N h — inte per session."
        ),
    )
    p.add_argument(
        "--billable-round",
        choices=["ceil", "nearest", "floor"],
        default="ceil",
        help=(
            "Bakåtkompatibilitet: ignoreras. Avrundning sker alltid uppåt (ceil) på aggregerad tid per projekt."
        ),
    )
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
    match_terms_input = as_list(raw.get("match_terms"))
    keywords = as_list(raw.get("keywords"))
    project_terms = as_list(raw.get("project_terms")) or [name]
    tracked_urls = as_list(raw.get("tracked_urls"))
    legacy_claude_urls = as_list(raw.get("claude_urls"))
    legacy_gemini_urls = as_list(raw.get("gemini_urls"))
    email = str(raw.get("email", "")).strip()
    customer = str(raw.get("customer", "")).strip() or name
    invoice_title = str(raw.get("invoice_title", "")).strip()
    invoice_description = str(raw.get("invoice_description", "")).strip()
    enabled = bool(raw.get("enabled", True))
    terms = sorted(
        {
            t.lower()
            for t in (match_terms_input + keywords + project_terms + [name])
            if t
        }
    )
    merged_tracked_urls = []
    seen_urls = set()
    for url in tracked_urls + legacy_claude_urls + legacy_gemini_urls:
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        merged_tracked_urls.append(url)
    return {
        "name": name,
        "enabled": enabled,
        "match_terms": terms,
        "keywords": keywords,
        "project_terms": project_terms,
        "tracked_urls": merged_tracked_urls,
        "email": email,
        "customer": customer,
        "invoice_title": invoice_title,
        "invoice_description": invoice_description,
    }


def load_profiles(config_path, args):
    cfg = Path(config_path)
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            workspace = {}
            if isinstance(data, dict):
                raw_profiles = data.get("projects", [])
                wl = data.get("worklog")
                if wl is not None and str(wl).strip():
                    workspace["worklog"] = str(wl).strip()
            elif isinstance(data, list):
                raw_profiles = data
            else:
                raise ValueError("JSON måste vara ett objekt eller en lista")
            profiles = [normalize_profile(p) for p in raw_profiles if bool(p.get("enabled", True))]
            if profiles:
                return profiles, cfg, workspace
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"[Varning] Kunde inte läsa projektkonfig {cfg}: {exc}")

    fallback = normalize_profile({
        "name": args.project,
        "keywords": as_list(args.keywords),
        "project_terms": [args.project],
        "claude_urls": as_list(args.claude_urls),
        "gemini_urls": [],
        "email": args.email,
    })
    return [fallback], None, {}


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
    return core_domain.classify_project(text, profiles, fallback)


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
            for ts, detail, _ in _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
                match_text = f"{dir_name} {detail}"
                project = classify_project(match_text, profiles)
                results.append(make_event("Claude Code CLI", ts, detail, project))
    return results


def collect_claude_desktop(profiles, dt_from, dt_to):
    results = []
    sessions_dir = HOME / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    if not sessions_dir.exists():
        return results

    for jsonl_file in sessions_dir.glob("**/*.jsonl"):
        for ts, detail, _ in _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
            # Endast synligt innehåll — hela JSON-raden innehåller ofta base64/id där
            # korta nyckelord (t.ex. "nud") träffar av misstag.
            match_text = detail
            project = classify_project(match_text, profiles)
            results.append(make_event("Claude Desktop", ts, detail, project))
    return results


def _query_chrome(where_clause, dt_from_cu, dt_to_cu):
    history_path = (
        HOME / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
    )
    return chrome_collector.query_chrome(history_path, where_clause, dt_from_cu, dt_to_cu)


def _chrome_time_range(dt_from, dt_to):
    return chrome_collector.chrome_time_range(dt_from, dt_to, CHROME_EPOCH_DELTA_US)


def _chrome_ts(visit_time_cu):
    return chrome_collector.chrome_ts(visit_time_cu, CHROME_EPOCH_DELTA_US)


def _normalize_chrome_url(url):
    return chrome_collector.normalize_chrome_url(url)


def _thin_chrome_visit_rows(rows, collapse_minutes):
    return chrome_collector.thin_chrome_visit_rows(rows, collapse_minutes, CHROME_EPOCH_DELTA_US)


def collect_claude_ai_urls(profiles, dt_from, dt_to):
    return chrome_collector.collect_claude_ai_urls(
        profiles,
        dt_from,
        dt_to,
        HOME,
        CHROME_EPOCH_DELTA_US,
        UNCATEGORIZED,
        make_event,
    )


def collect_gemini_web_urls(profiles, dt_from, dt_to):
    return chrome_collector.collect_gemini_web_urls(
        profiles,
        dt_from,
        dt_to,
        HOME,
        CHROME_EPOCH_DELTA_US,
        UNCATEGORIZED,
        make_event,
    )


def collect_chrome(profiles, dt_from, dt_to, collapse_minutes=0):
    return chrome_collector.collect_chrome(
        profiles,
        dt_from,
        dt_to,
        collapse_minutes,
        HOME,
        CHROME_EPOCH_DELTA_US,
        classify_project,
        make_event,
    )


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
    logs_dir = HOME / "Library" / "Application Support" / "Cursor" / "logs"
    if not logs_dir.exists():
        return []

    results = []
    # Cursor 3 har börjat logga fler "workspacePath"/"cwd" direkt och inte alltid workspaceStorage/<id>.
    # Vi stödjer både det gamla id-mönstret (via workspaceStorage-map) och direkt path-extraktion.
    ts_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    ts_iso_bracket_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})?\]")
    workspace_id_pattern = re.compile(r"workspaceStorage/([0-9a-f]{32})|old id ([0-9a-f]{32})-")
    # Plocka absolut sökväg från typiska Cursor 3-loggrader:
    # - ..."cwd":"/Users/.../some-repo"...
    # - ..."workspacePaths":["/Users/.../some-repo"]...
    # - "Project config path (...): /Users/.../some-repo/.cursor/hooks.json"
    # Vi matchar brett men filtrerar senare via classify_project().
    workspace_path_pattern = re.compile(r"(/Users/[^\"'\s]+)")

    def _parse_cursor_log_ts(line: str):
        m = ts_pattern.match(line)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOCAL_TZ)
            except ValueError:
                return None
        m = ts_iso_bracket_pattern.match(line)
        if m:
            iso = m.group(1) + (m.group(2) or "")
            # fromisoformat kräver +00:00 istället för Z
            iso = iso.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(iso)
            except ValueError:
                return None
        return None

    for log_file in logs_dir.glob("**/*.log"):
        try:
            with open(log_file, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    ts = _parse_cursor_log_ts(line)
                    if not ts:
                        continue
                    if not (dt_from <= ts <= dt_to):
                        continue

                    workspace_path = None
                    m_id = workspace_id_pattern.search(line)
                    if m_id and workspace_map:
                        workspace_id = m_id.group(1) or m_id.group(2)
                        workspace_path = workspace_map.get(workspace_id)

                    if not workspace_path:
                        # Välj första rimliga absoluta path på raden.
                        m_path = workspace_path_pattern.search(line)
                        if m_path:
                            workspace_path = m_path.group(1)

                    if not workspace_path:
                        continue

                    project = classify_project(f"{workspace_path} {line}", profiles)
                    detail = f"{Path(workspace_path).name} — {line.strip()[:90]}"
                    results.append(make_event("Cursor", ts, detail, project))
        except OSError:
            continue

    return results


def collect_cursor_checkpoints(profiles, dt_from, dt_to):
    """
    Checkpoints under Cursor → globalStorage → anysphere.cursor-commits (Cursor som app).
    Källnamnet CURSOR_CHECKPOINTS_SOURCE skiljer från OpenAI Codex IDE (collect_codex_ide).
    """
    if not CURSOR_CHECKPOINTS_DIR.is_dir():
        return []

    workspace_map = load_cursor_workspaces()
    results = []
    for meta_path in CURSOR_CHECKPOINTS_DIR.glob("*/metadata.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        ms = data.get("startTrackingDateUnixMilliseconds")
        if ms is None:
            continue
        try:
            ts = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            continue
        if not (dt_from <= ts <= dt_to):
            continue

        paths = []
        for rf in data.get("requestFiles") or []:
            p = rf.get("fsPath")
            if p:
                paths.append(str(p))
        wid = data.get("workspaceId")
        if wid:
            mapped = workspace_map.get(wid)
            if mapped:
                paths.append(str(mapped))

        hay = " ".join(paths)
        if not hay:
            continue

        project = classify_project(hay, profiles)
        agent_id = str(data.get("agentRequestId", "")).split("-")[0][:8]
        label = Path(paths[0]).name if paths else "checkpoint"
        detail = f"checkpoint {agent_id}… — {label}"
        results.append(make_event(CURSOR_CHECKPOINTS_SOURCE, ts, detail, project))

    return results


def collect_codex_ide(profiles, dt_from, dt_to):
    """
    OpenAI Codex IDE (fristående app): session_index.jsonl under ~/.codex/.
    En rad per tråd (thread_name, updated_at). Tidsstämpeln är senaste uppdatering — inte varje meddelande.
    Skilt från Cursor (logs + Cursor checkpoints).
    """
    if not CODEX_IDE_SESSION_INDEX.is_file():
        return []
    results = []
    try:
        text = CODEX_IDE_SESSION_INDEX.read_text(encoding="utf-8")
    except OSError:
        return []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts_raw = obj.get("updated_at")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if not (dt_from <= ts <= dt_to):
            continue
        thread = str(obj.get("thread_name") or "").strip() or "session"
        sid = str(obj.get("id") or "").replace("-", "")[:10]
        detail = f"{thread[:65]} — id {sid}…" if sid else thread[:70]
        project = classify_project(thread, profiles)
        results.append(make_event("Codex IDE", ts, detail, project))
    return results


def collect_worklog(worklog_path, dt_from, dt_to, profiles):
    return timelog_collector.collect_timelog(
        worklog_path,
        dt_from,
        dt_to,
        profiles,
        LOCAL_TZ,
        classify_project,
        make_event,
        WORKLOG_SOURCE,
    )


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


def compute_sessions(entries, gap_minutes=15):
    return core_domain.compute_sessions(entries, gap_minutes)


def session_duration_hours(session_events, start_ts, end_ts, min_session_minutes, min_session_passive_minutes):
    return core_domain.session_duration_hours(
        session_events,
        start_ts,
        end_ts,
        min_session_minutes,
        min_session_passive_minutes,
        AI_SOURCES,
    )


def billable_total_hours(raw_hours, unit):
    """Avrunda aggregerad tid uppåt till närmaste multipel av unit (t.ex. 0.25 h). unit<=0 = ingen avrundning."""
    return core_domain.billable_total_hours(raw_hours, unit)


def estimate_hours_by_day(
    days,
    gap_minutes,
    min_session_minutes,
    min_session_passive_minutes,
):
    per_day = {}
    for day, entries in days.items():
        sessions = compute_sessions(entries, gap_minutes=gap_minutes)
        total_h = 0.0
        for start, end, events in sessions:
            raw = session_duration_hours(
                events, start, end, min_session_minutes, min_session_passive_minutes
            )
            total_h += raw
        per_day[day] = {"entries": entries, "sessions": sessions, "hours": total_h}
    return per_day


def print_source_summary(events):
    """Antal händelser per källa efter dedupe/projektfilter — bra för att skilja IDE-loggar från checkpoints."""
    counts = defaultdict(int)
    for e in events:
        counts[e["source"]] += 1
    print("\n── Källsammanfattning (efter filter & dedupe, före sessioner) ──")
    for src in sorted(counts, key=lambda s: SOURCE_ORDER.index(s) if s in SOURCE_ORDER else 99):
        print(f"  {src}: {counts[src]}")
    print(f"  Summa: {sum(counts.values())}")
    print("──\n")


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
            raw_dur = session_duration_hours(
                session_events, start_ts, end_ts,
                args.min_session, args.min_session_passive
            )
            session_projects = sorted({event["project"] for event in session_events})
            print(
                f"    [{idx}] {start_ts.strftime('%H:%M')}–{end_ts.strftime('%H:%M')} "
                f"({raw_dur:.1f}h, {len(session_events)} händelser, {', '.join(session_projects)})"
            )
            if args.all_events:
                for event in session_events:
                    print(
                        f"        · {event['local_ts'].strftime('%H:%M:%S')}  "
                        f"[{event['source']}] [{event['project']}]  {event['detail']}"
                    )
            else:
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
    print(f"  TOTALT ESTIMERAT (råtid):  ~{total_h:.1f}h")
    if args.billable_unit and args.billable_unit > 0:
        grand_billable = sum(
            billable_total_hours(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                args.billable_unit,
            )
            for pn in project_reports
        )
        print(
            f"  FAKTURERBAR SUMMA (per projekt, upp till {args.billable_unit:g} h):  ~{grand_billable:.2f}h"
        )
    if screen_time_days is not None:
        screen_total_h = sum(screen_time_days.values()) / 3600
        print(f"  SCREEN TIME TOTALT: ~{screen_total_h:.1f}h")
        print(f"  DELTA:              {total_h - screen_total_h:+.1f}h")
    print(sep)
    print()

    profile_by_name = {p["name"]: p for p in profiles}
    projects_by_customer = defaultdict(list)
    for project_name in sorted(project_reports):
        customer = str(profile_by_name.get(project_name, {}).get("customer") or project_name)
        projects_by_customer[customer].append(project_name)

    print("Per kund:")
    for customer_name in sorted(projects_by_customer, key=lambda name: name.lower()):
        customer_projects = projects_by_customer[customer_name]
        customer_hours = sum(
            sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            for project_name in customer_projects
        )
        if args.billable_unit and args.billable_unit > 0:
            cust_b = sum(
                billable_total_hours(
                    sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                    args.billable_unit,
                )
                for pn in customer_projects
            )
            print(f"  - {customer_name}: ~{cust_b:.2f}h fakturerbart (råtid ~{customer_hours:.1f}h)")
        else:
            print(f"  - {customer_name}: ~{customer_hours:.1f}h")
        for project_name in customer_projects:
            hours = sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            days = len(project_reports[project_name])
            if args.billable_unit and args.billable_unit > 0:
                hb = billable_total_hours(hours, args.billable_unit)
                print(
                    f"      · {project_name}: ~{hb:.2f}h fakturerbart (råtid ~{hours:.1f}h) över {days} dagar"
                )
            else:
                print(f"      · {project_name}: ~{hours:.1f}h över {days} dagar")
    print()
    print("  OBS: Totalen ovan är den sammanlagda tidslinjen över alla källor.")
    print(
        "  [Cursor] = Cursor IDE-loggar. [Cursor checkpoints] = Cursor-appens metadata."
        " [Codex IDE] = OpenAI:s Codex-app (~/.codex) — eget program, inte Cursor."
    )
    print("  Kör med --source-summary om du vill se exakt antal händelser per källa efter filter.")
    print(
        f"  Sessioner: luckor kortare än {args.gap_minutes} min räknas som samma pass; "
        f"Chrome tunnas (--chrome-collapse-minutes={args.chrome_collapse_minutes}, 0=av)."
    )
    if args.billable_unit and args.billable_unit > 0:
        print(
            f"  Fakturerbar avrundning: råtid summeras per projekt, sedan avrundas uppat (ceil) "
            f"till närmaste {args.billable_unit:g} h — inte per session."
        )
    print("  Timmar bygger på diskreta händelser (t.ex. Chrome-besök), inte på KnowledgeC per klick.")
    print("  Per projekt räknas på projektmärkta händelser och kan avvika från totalen.")
    print("  Worklog tolkas nu i lokal tid i stället för UTC.")
    if not args.include_uncategorized:
        print("  Oklassade händelser exkluderas från rapporten som standard.")
    if screen_time_days is not None:
        print("  Screen Time kommer från KnowledgeC app-usage och är en jämförelsesignal, inte facit.")
    print()


def _invoice_projects_line(profiles, project_reports, customer_name):
    """Textrad för PDF: vid kundfilter lista bara aktuella projekt, annars alla profiler."""
    if project_reports:
        return ", ".join(sorted(project_reports.keys()))
    if customer_name:
        wanted = customer_name.strip().lower()
        names = [
            p["name"]
            for p in profiles
            if str(p.get("customer") or p["name"]).strip().lower() == wanted
        ]
        return ", ".join(sorted(names)) if names else "—"
    return ", ".join(p["name"] for p in profiles)


def build_invoice_pdf(
    overall_days,
    project_reports,
    profiles,
    dt_from,
    dt_to,
    output_path,
    empty_note=None,
    customer_name=None,
    billable_unit=0.0,
):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError(
            "PDF-generering kraver reportlab. Installera med: python3 -m pip install reportlab"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "InvoiceBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    total_raw_hours = sum(day_payload["hours"] for day_payload in overall_days.values())
    if billable_unit and billable_unit > 0:
        invoice_total_billable = sum(
            billable_total_hours(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                billable_unit,
            )
            for pn in project_reports
        )
    else:
        invoice_total_billable = total_raw_hours
    profile_by_name = {profile["name"]: profile for profile in profiles}
    period_text = f"{dt_from.astimezone(LOCAL_TZ).date()} till {dt_to.astimezone(LOCAL_TZ).date()}"
    projects_text = _invoice_projects_line(profiles, project_reports, customer_name)

    elements = [
        Paragraph("Tidrapport - fakturaunderlag", title_style),
        Paragraph(f"<b>Period:</b> {period_text}", body_style),
    ]
    if customer_name:
        elements.append(
            Paragraph(f"<b>Kund:</b> {html_escape(customer_name.strip())}", body_style)
        )
    if billable_unit and billable_unit > 0:
        elements.extend(
            [
                Paragraph(f"<b>Projekt:</b> {html_escape(projects_text)}", body_style),
                Paragraph(
                    f"<b>Totalt fakturerbart:</b> {invoice_total_billable:.2f} timmar<br/>"
                    f"<i>Råtid under perioden: {total_raw_hours:.2f} h</i>",
                    body_style,
                ),
            ]
        )
    else:
        elements.extend(
            [
                Paragraph(f"<b>Projekt:</b> {html_escape(projects_text)}", body_style),
                Paragraph(f"<b>Totalt estimerat:</b> {total_raw_hours:.2f} timmar", body_style),
            ]
        )
    if empty_note:
        elements.append(Paragraph(f"<i>{html_escape(empty_note)}</i>", body_style))
    elements.append(Spacer(1, 16))

    project_rows = [[
        Paragraph("<b>Beskrivning av tjänst / Leverabel</b>", body_style),
        Paragraph("<b>Omfattning</b>", body_style),
    ]]
    for project_name in sorted(project_reports):
        day_payloads = project_reports[project_name]
        hours = sum(day_payload["hours"] for day_payload in day_payloads.values())
        if hours <= 0:
            continue
        display_hours = billable_total_hours(hours, billable_unit)

        profile = profile_by_name.get(project_name, {})
        invoice_title = str(profile.get("invoice_title", "")).strip()
        invoice_description = str(profile.get("invoice_description", "")).strip()

        if invoice_title or invoice_description:
            safe_title = html_escape(invoice_title or project_name)
            safe_description = html_escape(
                invoice_description or "Löpande implementation, analys och leverans inom projektet."
            )
            desc = f"<b>{safe_title}</b><br/>{safe_description}"
            project_rows.append(
                [Paragraph(desc, body_style), Paragraph(f"{display_hours:.2f} h", body_style)]
            )
            continue

        source_counts = defaultdict(int)
        sample_details = []
        for day_payload in day_payloads.values():
            for event in day_payload.get("entries", []):
                source_counts[event.get("source", "")] += 1
                detail = str(event.get("detail", "")).strip()
                if detail and detail not in sample_details:
                    sample_details.append(detail)
                if len(sample_details) >= 2:
                    break
            if len(sample_details) >= 2:
                break

        top_sources = sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        source_part = ", ".join(src for src, _ in top_sources if src) or "lokala arbetsloggar"
        examples_part = "; ".join(sample_details) if sample_details else "Löpande implementation, analys och iteration."
        safe_project_name = html_escape(project_name)
        safe_source_part = html_escape(source_part)
        safe_examples_part = html_escape(examples_part)
        desc = (
            f"<b>{safe_project_name}</b><br/>"
            f"Löpande arbete inom projektet, sammanställt från {safe_source_part}. "
            f"Exempel på utförda insatser: {safe_examples_part}"
        )
        project_rows.append(
            [Paragraph(desc, body_style), Paragraph(f"{display_hours:.2f} h", body_style)]
        )

    sum_hours = invoice_total_billable
    project_rows.append(
        [
            Paragraph("<b>Summa</b>", body_style),
            Paragraph(f"<b>{sum_hours:.2f} h</b>", body_style),
        ]
    )
    project_table = Table(project_rows, colWidths=[4.8 * inch, 1.3 * inch])
    project_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.lightgrey),
                ("LINEABOVE", (0, -1), (-1, -1), 0.9, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(project_table)
    elements.append(Spacer(1, 18))

    daily_rows = [[Paragraph("<b>Datum</b>", body_style), Paragraph("<b>Timmar</b>", body_style)]]
    for day in sorted(overall_days):
        daily_rows.append(
            [Paragraph(day, body_style), Paragraph(f"{overall_days[day]['hours']:.2f} h", body_style)]
        )
    daily_table = Table(daily_rows, colWidths=[4.8 * inch, 1.3 * inch])
    daily_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(Paragraph("<b>Daglig specifikation</b>", body_style))
    elements.append(Spacer(1, 8))
    elements.append(daily_table)
    if billable_unit and billable_unit > 0:
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(
                "<i>Dagliga timmar är råtid; fakturerbara belopp i tabellen ovan avrundas uppåt per projekt.</i>",
                body_style,
            )
        )

    doc.build(elements)
    return output_path


def collect_all_events(profiles, dt_from, dt_to, args, worklog_path):
    all_events = []
    collectors = [
        ("Claude Code CLI", collect_claude_code, "händelser"),
        ("Claude Desktop", collect_claude_desktop, "händelser"),
        ("Claude.ai (specifika URL:er)", collect_claude_ai_urls, "besök"),
        ("Gemini (webb, specifika URL:er)", collect_gemini_web_urls, "besök"),
        (
            "Chrome",
            lambda p, start, end: collect_chrome(
                p, start, end, collapse_minutes=args.chrome_collapse_minutes
            ),
            "besök",
        ),
        ("Gemini CLI", collect_gemini_cli, "händelser"),
        ("Cursor", collect_cursor, "händelser"),
        ("Cursor checkpoints", collect_cursor_checkpoints, "händelser"),
        ("Codex IDE (OpenAI ~/.codex)", collect_codex_ide, "sessioner"),
        (
            "Apple Mail",
            lambda p, start, end: collect_apple_mail(
                p, start, end, default_email=args.email
            ),
            "mail",
        ),
        (
            "TIMELOG.md",
            lambda p, start, end: collect_worklog(str(worklog_path), start, end, p),
            "timestamps",
        ),
    ]

    for index, (name, collector, unit_label) in enumerate(collectors, 1):
        print(f"[{index}/12] {name} …")
        events = collector(profiles, dt_from, dt_to)
        print(f"      {len(events)} {unit_label}\n")
        all_events.extend(events)
    return all_events


def filter_included_events(all_events, args, profiles):
    included_events = all_events if args.include_uncategorized else [
        event for event in all_events if event["project"] != UNCATEGORIZED
    ]
    if args.only_project:
        only = args.only_project.strip()
        included_events = [e for e in included_events if e["project"] == only]
    if args.customer:
        wanted_customer = args.customer.strip().lower()
        project_to_customer = {
            p["name"]: str(p.get("customer") or p["name"]).strip().lower()
            for p in profiles
        }
        allowed_projects = {
            project_name
            for project_name, customer_name in project_to_customer.items()
            if customer_name == wanted_customer
        }
        included_events = [e for e in included_events if e["project"] in allowed_projects]
    return included_events


def run_timelog_report(config_path, date_from, date_to, options):
    args = argparse.Namespace(**vars(options))
    args.projects_config = config_path
    args.date_from = date_from
    args.date_to = date_to

    if args.today:
        today_s = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        args.date_from = today_s
        args.date_to = today_s
    dt_from, dt_to = get_date_range(args.date_from, args.date_to)
    profiles, loaded_config_path, workspace = load_profiles(args.projects_config, args)
    worklog_path = resolve_worklog_path(
        args.worklog, loaded_config_path, workspace.get("worklog")
    )

    print(f"\nSöker: {dt_from.date()} → {dt_to.date()}")
    if args.only_project:
        print(f"Endast projekt: {args.only_project!r}")
    if args.customer:
        print(f"Endast kund: {args.customer!r}")
    print(f"Lokal tidszon: {LOCAL_TZ}")
    print(f"Projektprofiler: {len(profiles)}")
    print(f"Worklog: {worklog_path}")
    print()

    all_events = collect_all_events(profiles, dt_from, dt_to, args, worklog_path)

    screen_time_days = None
    print("[12/12] Screen Time …")
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
    included_events = filter_included_events(all_events, args, profiles)

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

    return ReportPayload(
        dt_from=dt_from,
        dt_to=dt_to,
        profiles=profiles,
        config_path=loaded_config_path,
        worklog_path=worklog_path,
        all_events=all_events,
        included_events=included_events,
        grouped=grouped,
        overall_days=overall_days,
        project_reports=project_reports,
        screen_time_days=screen_time_days,
        args=args,
    )


def generate_invoice_pdf(report_payload, output_path=None, options=None):
    args = options or report_payload.args
    if output_path is None:
        output_path = (
            Path(args.invoice_pdf_file).expanduser()
            if args.invoice_pdf_file
            else default_invoice_pdf_path(report_payload.dt_to)
        )
    return build_invoice_pdf(
        report_payload.overall_days,
        report_payload.project_reports,
        report_payload.profiles,
        report_payload.dt_from,
        report_payload.dt_to,
        output_path,
        customer_name=args.customer,
        billable_unit=args.billable_unit,
    )


def main():
    args = parse_args()
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, args)
    included_events = report.included_events

    if not included_events:
        if report.args.only_project:
            print(f"Inga händelser för projekt {report.args.only_project!r} i intervallet.")
        else:
            print("Inga händelser hittades.")
        if report.args.invoice_pdf:
            try:
                built = build_invoice_pdf(
                    {},
                    {},
                    report.profiles,
                    report.dt_from,
                    report.dt_to,
                    Path(report.args.invoice_pdf_file).expanduser()
                    if report.args.invoice_pdf_file
                    else default_invoice_pdf_path(report.dt_to),
                    empty_note=(
                        "Inga klassade händelser i valt intervall/filter — rapporten är tom (0 timmar)."
                    ),
                    customer_name=report.args.customer,
                    billable_unit=report.args.billable_unit,
                )
                print(f"PDF skapad: {built}")
            except Exception as exc:
                print(f"Kunde inte skapa PDF: {exc}")
        return

    if report.args.source_summary:
        print_source_summary(report.included_events)

    print_report(
        report.overall_days,
        report.project_reports,
        report.screen_time_days,
        report.profiles,
        report.args,
        report.config_path,
    )
    if report.args.invoice_pdf:
        try:
            built = generate_invoice_pdf(report)
            print(f"PDF skapad: {built}")
        except Exception as exc:
            print(f"Kunde inte skapa PDF: {exc}")


if __name__ == "__main__":
    main()
