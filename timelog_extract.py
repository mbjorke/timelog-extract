#!/usr/bin/env python3
"""
timelog_extract.py — Multi-project aggregator for local work logs
=================================================================

Summarizes daily activity from:
  1. Claude Code CLI (Claude for Mac, Code Agent — ~/.claude/projects/)
  2. Claude Desktop
  3. Claude.ai (specific chat URLs in Chrome history)
  4. Google Gemini in browser (specific app URLs)
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
from core.collector_registry import build_collector_specs
from core import domain as core_domain
from core.sources import AI_SOURCES, CURSOR_CHECKPOINTS_SOURCE, SOURCE_ORDER, WORKLOG_SOURCE
from outputs import pdf as pdf_output
from outputs import terminal as terminal_output

HOME = Path.home()
SCRIPT_DIR = Path(__file__).parent
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
APPLE_EPOCH = 978307200
CHROME_EPOCH_DELTA_US = 11_644_473_600 * 1_000_000

# Default settings
DEFAULT_KEYWORDS = ""
DEFAULT_PROJECT = "default-project"
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
CODEX_IDE_SESSION_INDEX = HOME / ".codex" / "session_index.jsonl"
UNCATEGORIZED = "Uncategorized"


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
    match_terms_input = as_list(raw.get("match_terms")) or [name]
    tracked_urls = as_list(raw.get("tracked_urls"))
    email = str(raw.get("email", "")).strip()
    customer = str(raw.get("customer", "")).strip() or name
    invoice_title = str(raw.get("invoice_title", "")).strip()
    invoice_description = str(raw.get("invoice_description", "")).strip()
    enabled = bool(raw.get("enabled", True))
    terms = sorted(
        {
            t.lower()
            for t in (match_terms_input + [name])
            if t
        }
    )
    merged_tracked_urls = sorted({url for url in tracked_urls if url})
    return {
        "name": name,
        "enabled": enabled,
        "match_terms": terms,
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

    fallback = normalize_profile(
        {
            "name": args.project,
            "match_terms": as_list(args.keywords) + [args.project],
            "email": args.email,
        }
    )
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
    terminal_output.print_source_summary(events, SOURCE_ORDER)


def print_report(overall_days, project_reports, screen_time_days, profiles, args, config_path):
    terminal_output.print_report(
        overall_days=overall_days,
        project_reports=project_reports,
        screen_time_days=screen_time_days,
        profiles=profiles,
        args=args,
        config_path=config_path,
        local_tz=LOCAL_TZ,
        source_order=SOURCE_ORDER,
        uncategorized=UNCATEGORIZED,
        session_duration_hours_fn=session_duration_hours,
        billable_total_hours_fn=billable_total_hours,
    )


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
    return pdf_output.build_invoice_pdf(
        overall_days=overall_days,
        project_reports=project_reports,
        profiles=profiles,
        dt_from=dt_from,
        dt_to=dt_to,
        output_path=output_path,
        local_tz=LOCAL_TZ,
        billable_total_hours_fn=billable_total_hours,
        empty_note=empty_note,
        customer_name=customer_name,
        billable_unit=billable_unit,
    )


def collect_all_events(profiles, dt_from, dt_to, args, worklog_path):
    all_events = []
    collector_status = {}
    chrome_history_exists = chrome_collector.chrome_history_path(HOME).exists()
    mail_root, mail_msg = mail_collector.detect_mail_root(HOME)
    collectors = build_collector_specs(
        args,
        worklog_path,
        chrome_history_exists=chrome_history_exists,
        mail_root=mail_root,
        mail_msg=mail_msg,
        collect_claude_code=collect_claude_code,
        collect_claude_desktop=collect_claude_desktop,
        collect_claude_ai_urls=collect_claude_ai_urls,
        collect_gemini_web_urls=collect_gemini_web_urls,
        collect_chrome=collect_chrome,
        collect_gemini_cli=collect_gemini_cli,
        collect_cursor=collect_cursor,
        collect_cursor_checkpoints=collect_cursor_checkpoints,
        collect_codex_ide=collect_codex_ide,
        collect_apple_mail=collect_apple_mail,
        collect_worklog=collect_worklog,
    )

    for index, spec in enumerate(collectors, 1):
        name = spec.name
        collector = spec.collector
        unit_label = spec.unit_label
        enabled = spec.enabled
        reason = spec.reason
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
