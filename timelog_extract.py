#!/usr/bin/env python3
"""
timelog_extract.py — Multi-project aggregator for local work logs
=================================================================

Summarizes daily activity from:
  1. Claude Code CLI (Claude for Mac, Code Agent — ~/.claude/projects/)
  2. Claude Desktop
  3. Claude.ai (specific chat URLs in Chrome history)
  4. Google Gemini in browser (specific app URLs, similar to claude_urls)
  5. Chrome (project matching via terms)
  6. Gemini CLI (local JSON sessions under ~/.gemini/tmp)
  7. Cursor (IDE logs)
  8. Cursor checkpoints (Cursor app -> .../cursor-commits/checkpoints)
  9. Codex IDE (OpenAI app — ~/.codex/session_index.jsonl)
  10. Apple Mail
  11. TIMELOG.md
  12. Screen Time / KnowledgeC (optional comparison)

Projects are defined through a JSON config file. If no config is available,
a backward-compatible default project from CLI arguments is used.
"""

import argparse
import json
import os
import shutil
import sqlite3
import tempfile
from html import escape as html_escape
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from collectors import ai_logs as ai_logs_collector
from collectors import chrome as chrome_collector
from collectors import cursor as cursor_collector
from collectors import mail as mail_collector
from collectors import timelog as timelog_collector
from core import domain as core_domain

HOME = Path.home()
SCRIPT_DIR = Path(__file__).parent
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
APPLE_EPOCH = 978307200
CHROME_EPOCH_DELTA_US = 11_644_473_600 * 1_000_000

# Default settings
DEFAULT_KEYWORDS = ""
DEFAULT_PROJECT = "default-project"
DEFAULT_CLAUDE_URLS = ""
DEFAULT_EMAIL = ""
DEFAULT_EXCLUDE = ""
DEFAULT_CONFIG = str(SCRIPT_DIR / "timelog_projects.json")


def default_worklog_path() -> Path:
    """Default timelog file in the project: TIMELOG.md."""
    cwd = Path.cwd() / "TIMELOG.md"
    if cwd.is_file():
        return cwd
    local = SCRIPT_DIR / "TIMELOG.md"
    if local.is_file():
        return local
    return SCRIPT_DIR / "TIMELOG.md"


def resolve_worklog_path(cli_worklog, config_path, workspace_worklog):
    """
    cli_worklog: None when --worklog is not provided (uses JSON worklog first, then default).
    workspace_worklog: optional string value from the root object in timelog_projects.json.
    Relative paths in JSON are resolved against the config file directory.
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
UNCATEGORIZED = "Uncategorized"
# Cursor app agent checkpoints; separate from "Cursor" logs and OpenAI Codex IDE (~/.codex).
CURSOR_CHECKPOINTS_SOURCE = "Cursor checkpoints"
WORKLOG_SOURCE = "TIMELOG.md"

SOURCE_ORDER = [
    "Claude Code CLI",
    "Claude Desktop",
    "Claude.ai (web)",
    "Gemini (web)",
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
    "Claude.ai (web)",
    "Gemini (web)",
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
    collector_status: Dict[str, Dict[str, Any]]
    args: argparse.Namespace


@dataclass
class TimelogRunOptions:
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    today: bool = False
    projects_config: str = DEFAULT_CONFIG
    keywords: str = DEFAULT_KEYWORDS
    project: str = DEFAULT_PROJECT
    claude_urls: str = DEFAULT_CLAUDE_URLS
    email: str = DEFAULT_EMAIL
    min_session: int = 15
    min_session_passive: int = 5
    gap_minutes: int = 15
    chrome_collapse_minutes: int = 12
    exclude: str = DEFAULT_EXCLUDE
    worklog: Optional[str] = None
    screen_time: str = "auto"
    include_uncategorized: bool = False
    only_project: Optional[str] = None
    customer: Optional[str] = None
    all_events: bool = False
    source_summary: bool = False
    invoice_pdf: bool = False
    invoice_pdf_file: Optional[str] = None
    billable_unit: float = 0.0
    billable_round: str = "ceil"
    chrome_source: str = "on"
    mail_source: str = "auto"


def as_run_options(options: Any) -> TimelogRunOptions:
    allowed_fields = set(TimelogRunOptions.__dataclass_fields__.keys())
    if isinstance(options, TimelogRunOptions):
        return options
    if isinstance(options, argparse.Namespace):
        raw = vars(options)
        return TimelogRunOptions(**{k: v for k, v in raw.items() if k in allowed_fields})
    if isinstance(options, dict):
        return TimelogRunOptions(**{k: v for k, v in options.items() if k in allowed_fields})
    raise TypeError(f"Unsupported options type: {type(options)!r}")


def default_invoice_pdf_path(dt_to):
    stamp = dt_to.astimezone(LOCAL_TZ).date().isoformat()
    return SCRIPT_DIR / "output" / "pdf" / f"timelog-invoice-{stamp}.pdf"


def parse_args():
    p = argparse.ArgumentParser(
        description="Aggregate work time from multiple local sources and projects"
    )
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                   help="Start date in local time (default: 30 days ago)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                   help="End date in local time (default: today)")
    p.add_argument("--projects-config", default=DEFAULT_CONFIG,
                   help=f"JSON config with project profiles (default: {DEFAULT_CONFIG})")
    p.add_argument("--keywords", default=DEFAULT_KEYWORDS,
                   help="Legacy fallback: comma-separated project keywords")
    p.add_argument("--project", default=DEFAULT_PROJECT,
                   help="Legacy fallback: project name for AI logs")
    p.add_argument("--claude-urls", default=DEFAULT_CLAUDE_URLS,
                   help="Legacy fallback: kommaseparerade Claude.ai chatt-URL:er")
    p.add_argument("--email", default=DEFAULT_EMAIL,
                   help=f"Legacy fallback: sender email for sent mail (default: {DEFAULT_EMAIL})")
    p.add_argument("--min-session", dest="min_session", type=int, default=15,
                   help="Minimitid i minuter per AI-session (default: 15)")
    p.add_argument("--min-session-passive", dest="min_session_passive", type=int, default=5,
                   help="Minimum duration in minutes for Chrome/Mail-only sessions (default: 5)")
    p.add_argument("--gap-minutes", type=int, default=15,
                   help="Gaps shorter than N minutes are merged into one session (default: 15)")
    p.add_argument("--chrome-collapse-minutes", type=int, default=12,
                   help="Skip repeated Chrome visits to the same page within N minutes (0=off; reduces refresh noise)")
    p.add_argument(
        "--chrome-source",
        choices=["on", "off"],
        default="on",
        help="Explicitly enable/disable Chrome source (default: on).",
    )
    p.add_argument(
        "--mail-source",
        choices=["auto", "on", "off"],
        default="auto",
        help="Enable/disable Apple Mail source (default: auto).",
    )
    p.add_argument("--exclude", default=DEFAULT_EXCLUDE,
                   help="Kommaseparerade ord att filtrera bort")
    p.add_argument(
        "--worklog",
        default=None,
        metavar="PATH",
        help="Path to timelog file (default: TIMELOG.md in repo root)",
    )
    p.add_argument("--screen-time", choices=["auto", "on", "off"], default="auto",
                   help="Compare with Screen Time when possible (default: auto)")
    p.add_argument("--include-uncategorized", action="store_true",
                   help="Include uncategorized events in the report")
    p.add_argument(
        "--only-project",
        metavar="NAMN",
        default=None,
        help="Show only events for this project (exact string as 'name' in JSON)",
    )
    p.add_argument(
        "--customer",
        metavar="NAMN",
        default=None,
        help="Show only events for this customer (matches 'customer' in JSON, otherwise project name)",
    )
    p.add_argument(
        "--today",
        action="store_true",
        help="Limit to today in local timezone (--from and --to both set to today)",
    )
    p.add_argument(
        "--all-events",
        action="store_true",
        help="Print every event per session (otherwise max 5 distinct lines per session)",
    )
    p.add_argument(
        "--source-summary",
        action="store_true",
        help="Print event counts per source after filtering (IDE logs vs checkpoints, etc.)",
    )
    p.add_argument(
        "--invoice-pdf",
        action="store_true",
        help="Create an invoice-friendly PDF summary of hours",
    )
    p.add_argument(
        "--invoice-pdf-file",
        default=None,
        help="Optional file path for PDF (default: output/pdf/timelog-invoice-<date>.pdf)",
    )
    p.add_argument(
        "--billable-unit",
        type=float,
        default=0.0,
        metavar="TIMMAR",
        help=(
            "Billable granularity (0=off, e.g. 0.25): raw time is summed per project/customer first, "
            "then rounded up to the nearest N hours — not per session."
        ),
    )
    p.add_argument(
        "--billable-round",
        choices=["ceil", "nearest", "floor"],
        default="ceil",
        help=(
            "Backward compatibility: ignored. Rounding is always upward (ceil) on aggregated project time."
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
        raise ValueError("Each project profile must have 'name'")
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
                raise ValueError("JSON must be an object or a list")
            profiles = [normalize_profile(p) for p in raw_profiles if bool(p.get("enabled", True))]
            if profiles:
                return profiles, cfg, workspace
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"[Warning] Could not read project config {cfg}: {exc}")

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


def collect_claude_code(profiles, dt_from, dt_to):
    return ai_logs_collector.collect_claude_code(
        profiles, dt_from, dt_to, HOME, classify_project, make_event
    )


def collect_claude_desktop(profiles, dt_from, dt_to):
    return ai_logs_collector.collect_claude_desktop(
        profiles, dt_from, dt_to, HOME, classify_project, make_event
    )


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
    return mail_collector.collect_apple_mail(
        profiles,
        dt_from,
        dt_to,
        HOME,
        default_email,
        classify_project,
        make_event,
        UNCATEGORIZED,
    )


def collect_gemini_cli(profiles, dt_from, dt_to):
    return ai_logs_collector.collect_gemini_cli(
        profiles, dt_from, dt_to, HOME, classify_project, make_event
    )


def load_cursor_workspaces():
    return cursor_collector.load_cursor_workspaces(HOME)


def collect_cursor(profiles, dt_from, dt_to):
    return cursor_collector.collect_cursor(
        profiles, dt_from, dt_to, HOME, LOCAL_TZ, classify_project, make_event
    )


def collect_cursor_checkpoints(profiles, dt_from, dt_to):
    return cursor_collector.collect_cursor_checkpoints(
        profiles,
        dt_from,
        dt_to,
        CURSOR_CHECKPOINTS_DIR,
        HOME,
        classify_project,
        make_event,
        CURSOR_CHECKPOINTS_SOURCE,
    )


def collect_codex_ide(profiles, dt_from, dt_to):
    return ai_logs_collector.collect_codex_ide(
        profiles,
        dt_from,
        dt_to,
        CODEX_IDE_SESSION_INDEX,
        classify_project,
        make_event,
    )


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
        return None, "knowledgeC.db not found"

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
        return None, f"could not read Screen Time database: {exc}"
    except PermissionError:
        return None, "no access to knowledgeC.db"
    except Exception as exc:
        return None, f"Screen Time read failed: {exc}"
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
    """Round aggregated time up to nearest unit multiple (e.g. 0.25 h). unit<=0 means no rounding."""
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
    """Event count per source after dedupe/project filtering."""
    counts = defaultdict(int)
    for e in events:
        counts[e["source"]] += 1
    print("\n-- Source summary (after filtering & dedupe, before sessions) --")
    for src in sorted(counts, key=lambda s: SOURCE_ORDER.index(s) if s in SOURCE_ORDER else 99):
        print(f"  {src}: {counts[src]}")
    print(f"  Total: {sum(counts.values())}")
    print("--\n")


def print_report(overall_days, project_reports, screen_time_days, profiles, args, config_path):
    sep = "─" * 64
    print(f"\n{'═' * 64}")
    print("  TIMELOGS — SUMMARY")
    print(f"{'═' * 64}\n")

    if config_path:
        print(f"Project config: {config_path}")
    else:
        print("Project config: legacy fallback from CLI arguments")
    print(f"Local timezone: {LOCAL_TZ}")
    print(f"Projects: {', '.join(profile['name'] for profile in profiles)}")
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
        print(f"    Sessions: {len(payload['sessions'])}  -> estimated ~{payload['hours']:.1f}h")
        print(f"    Sources:   {', '.join(sources)}")
        print(f"    Projects:  {', '.join(project_names) if project_names else UNCATEGORIZED}")
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
                f"({raw_dur:.1f}h, {len(session_events)} events, {', '.join(session_projects)})"
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
                            print(f"          … and {remaining} more")
                        break
        print()

    print(sep)
    print(f"  TOTAL ESTIMATED (raw time):  ~{total_h:.1f}h")
    if args.billable_unit and args.billable_unit > 0:
        grand_billable = sum(
            billable_total_hours(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                args.billable_unit,
            )
            for pn in project_reports
        )
        print(
            f"  BILLABLE TOTAL (per project, rounded to {args.billable_unit:g} h):  ~{grand_billable:.2f}h"
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

    print("Per customer:")
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
            print(f"  - {customer_name}: ~{cust_b:.2f}h billable (raw ~{customer_hours:.1f}h)")
        else:
            print(f"  - {customer_name}: ~{customer_hours:.1f}h")
        for project_name in customer_projects:
            hours = sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            days = len(project_reports[project_name])
            if args.billable_unit and args.billable_unit > 0:
                hb = billable_total_hours(hours, args.billable_unit)
                print(
                    f"      · {project_name}: ~{hb:.2f}h billable (raw ~{hours:.1f}h) across {days} days"
                )
            else:
                print(f"      · {project_name}: ~{hours:.1f}h across {days} days")
    print()
    print("  NOTE: Total above is the combined timeline across all sources.")
    print(
        "  [Cursor] = Cursor IDE logs. [Cursor checkpoints] = Cursor app metadata."
        " [Codex IDE] = OpenAI Codex app (~/.codex) — separate program, not Cursor."
    )
    print("  Run with --source-summary to see exact event count per source after filters.")
    print(
        f"  Sessions: gaps shorter than {args.gap_minutes} min are merged; "
        f"Chrome is deduplicated (--chrome-collapse-minutes={args.chrome_collapse_minutes}, 0=off)."
    )
    if args.billable_unit and args.billable_unit > 0:
        print(
            f"  Billable rounding: raw time is summed per project, then rounded up (ceil) "
            f"to the nearest {args.billable_unit:g} h — not per session."
        )
    print("  Hours are based on discrete events (e.g. Chrome visits), not on per-click KnowledgeC usage.")
    print("  Per-project totals use project-tagged events and may differ from the grand total.")
    print("  Worklog is interpreted in local time instead of UTC.")
    if not args.include_uncategorized:
        print("  Uncategorized events are excluded from report by default.")
    if screen_time_days is not None:
        print("  Screen Time comes from KnowledgeC app usage and is a comparison signal, not ground truth.")
    print()


def _invoice_projects_line(profiles, project_reports, customer_name):
    """PDF line text: with customer filter list active projects only, otherwise all profiles."""
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
            "PDF generation requires reportlab. Install with: python3 -m pip install reportlab"
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
    period_text = f"{dt_from.astimezone(LOCAL_TZ).date()} to {dt_to.astimezone(LOCAL_TZ).date()}"
    projects_text = _invoice_projects_line(profiles, project_reports, customer_name)

    elements = [
        Paragraph("Time report - invoice basis", title_style),
        Paragraph(f"<b>Period:</b> {period_text}", body_style),
    ]
    if customer_name:
        elements.append(
            Paragraph(f"<b>Kund:</b> {html_escape(customer_name.strip())}", body_style)
        )
    if billable_unit and billable_unit > 0:
        elements.extend(
            [
                Paragraph(f"<b>Projects:</b> {html_escape(projects_text)}", body_style),
                Paragraph(
                    f"<b>Total billable:</b> {invoice_total_billable:.2f} hours<br/>"
                    f"<i>Raw time in period: {total_raw_hours:.2f} h</i>",
                    body_style,
                ),
            ]
        )
    else:
        elements.extend(
            [
                Paragraph(f"<b>Projects:</b> {html_escape(projects_text)}", body_style),
                Paragraph(f"<b>Total estimated:</b> {total_raw_hours:.2f} hours", body_style),
            ]
        )
    if empty_note:
        elements.append(Paragraph(f"<i>{html_escape(empty_note)}</i>", body_style))
    elements.append(Spacer(1, 16))

    project_rows = [[
        Paragraph("<b>Service description / Deliverable</b>", body_style),
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
                invoice_description or "Ongoing implementation, analysis, and delivery within the project."
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
        source_part = ", ".join(src for src, _ in top_sources if src) or "local work logs"
        examples_part = "; ".join(sample_details) if sample_details else "Ongoing implementation, analysis, and iteration."
        safe_project_name = html_escape(project_name)
        safe_source_part = html_escape(source_part)
        safe_examples_part = html_escape(examples_part)
        desc = (
            f"<b>{safe_project_name}</b><br/>"
            f"Ongoing project work, aggregated from {safe_source_part}. "
            f"Examples of delivered work: {safe_examples_part}"
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
                "<i>Daily hours are raw time; billable values in the table above are rounded up per project.</i>",
                body_style,
            )
        )

    doc.build(elements)
    return output_path


def collect_all_events(profiles, dt_from, dt_to, args, worklog_path):
    all_events = []
    collector_status = {}
    chrome_history_exists = chrome_collector.chrome_history_path(HOME).exists()
    mail_root, mail_msg = mail_collector.detect_mail_root(HOME)
    chrome_enabled = getattr(args, "chrome_source", "on") == "on"
    mail_mode = getattr(args, "mail_source", "auto")
    mail_enabled = mail_mode in {"on", "auto"}

    collectors = [
        ("Claude Code CLI", collect_claude_code, "events"),
        ("Claude Desktop", collect_claude_desktop, "events"),
        ("Claude.ai (specific URLs)", collect_claude_ai_urls, "visits"),
        ("Gemini (web, specific URLs)", collect_gemini_web_urls, "visits"),
        (
            "Chrome",
            lambda p, start, end: collect_chrome(
                p, start, end, collapse_minutes=args.chrome_collapse_minutes
            ),
            "visits",
            chrome_enabled,
            "Consent/source setting disabled" if not chrome_enabled else (
                None if chrome_history_exists else "Chrome history database not found"
            ),
        ),
        ("Gemini CLI", collect_gemini_cli, "events"),
        ("Cursor", collect_cursor, "events"),
        ("Cursor checkpoints", collect_cursor_checkpoints, "events"),
        ("Codex IDE (OpenAI ~/.codex)", collect_codex_ide, "sessions"),
        (
            "Apple Mail",
            lambda p, start, end: collect_apple_mail(
                p, start, end, default_email=args.email
            ),
            "mail",
            mail_enabled,
            "Consent/source setting disabled" if not mail_enabled else (
                None if mail_root is not None else mail_msg
            ),
        ),
        (
            "TIMELOG.md",
            lambda p, start, end: collect_worklog(str(worklog_path), start, end, p),
            "timestamps",
            True,
            None,
        ),
    ]

    normalized_collectors = []
    for collector in collectors:
        if len(collector) == 3:
            name, fn, unit_label = collector
            normalized_collectors.append((name, fn, unit_label, True, None))
        else:
            normalized_collectors.append(collector)

    for index, (name, collector, unit_label, enabled, reason) in enumerate(normalized_collectors, 1):
        print(f"[{index}/12] {name} …")
        if not enabled:
            print(f"      disabled ({reason})\n")
            collector_status[name] = {
                "enabled": False,
                "reason": reason,
                "events": 0,
            }
            continue
        events = collector(profiles, dt_from, dt_to)
        print(f"      {len(events)} {unit_label}\n")
        all_events.extend(events)
        collector_status[name] = {
            "enabled": True,
            "reason": reason or "",
            "events": len(events),
        }
    return all_events, collector_status


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
    run_options = as_run_options(options)
    args = argparse.Namespace(**vars(run_options))
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

    print(f"\nScanning: {dt_from.date()} -> {dt_to.date()}")
    if args.only_project:
        print(f"Only project: {args.only_project!r}")
    if args.customer:
        print(f"Only customer: {args.customer!r}")
    print(f"Local timezone: {LOCAL_TZ}")
    print(f"Project profiles: {len(profiles)}")
    print(f"Worklog: {worklog_path}")
    print()

    all_events, collector_status = collect_all_events(profiles, dt_from, dt_to, args, worklog_path)

    screen_time_days = None
    print("[12/12] Screen Time …")
    if args.screen_time == "off":
        print("      disabled via --screen-time off\n")
        collector_status["Screen Time"] = {
            "enabled": False,
            "reason": "disabled via --screen-time off",
            "days": 0,
        }
    else:
        screen_time_days, screen_msg = collect_screen_time(dt_from, dt_to)
        if screen_time_days is None:
            if args.screen_time == "on":
                print(f"      could not read Screen Time: {screen_msg}\n")
            else:
                print(f"      skipping: {screen_msg}\n")
            collector_status["Screen Time"] = {
                "enabled": args.screen_time == "on",
                "reason": screen_msg,
                "days": 0,
            }
        else:
            print(f"      {len(screen_time_days)} days loaded from {screen_msg}\n")
            collector_status["Screen Time"] = {
                "enabled": True,
                "reason": "",
                "days": len(screen_time_days),
            }

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
        collector_status=collector_status,
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
            print(f"No events for project {report.args.only_project!r} in selected range.")
        else:
            print("No events found.")
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
                        "No classified events for selected range/filter — report is empty (0 hours)."
                    ),
                    customer_name=report.args.customer,
                    billable_unit=report.args.billable_unit,
                )
                print(f"PDF created: {built}")
            except Exception as exc:
                print(f"Could not create PDF: {exc}")
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
            print(f"PDF created: {built}")
        except Exception as exc:
            print(f"Could not create PDF: {exc}")


if __name__ == "__main__":
    main()
