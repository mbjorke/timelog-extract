"""Runtime orchestration helpers for report service boundaries."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from core.noise_profiles import (
    DEFAULT_LOVABLE_NOISE_PROFILE,
    DEFAULT_NOISE_PROFILE,
    LOVABLE_NOISE_PROFILES,
    NOISE_PROFILES,
)

from collectors import ai_logs as ai_logs_collector
from collectors import chrome as chrome_collector
from collectors import cursor as cursor_collector
from collectors import github as github_collector
from collectors import mail as mail_collector
from collectors import timelog as timelog_collector
from collectors import toggl as toggl_collector
from core.collector_registry import build_collector_specs
from core.pipeline import collect_all_events
from core.runtime_collectors import RuntimeCollectors


def _resolve_only_project_filter(args: argparse.Namespace, profiles: List[Dict[str, Any]]) -> None:
    requested = str(getattr(args, "only_project", "") or "").strip()
    if not requested:
        return
    by_name = {str(p.get("name", "")).strip().lower(): str(p.get("name", "")).strip() for p in profiles if str(p.get("name", "")).strip()}
    exact = by_name.get(requested.lower())
    if exact:
        args.only_project = exact
        return

    candidates: list[str] = []
    seen: set[str] = set()
    needle = requested.lower()
    for profile in profiles:
        canonical = str(profile.get("name", "")).strip()
        if not canonical:
            continue
        names = [canonical] + [str(a).strip() for a in (profile.get("aliases") or []) if str(a).strip()]
        if any(needle in name.lower() for name in names):
            key = canonical.lower()
            if key not in seen:
                seen.add(key)
                candidates.append(canonical)
    if len(candidates) == 1:
        args.only_project_input = requested
        args.only_project = candidates[0]
        args.only_project_resolved = True
        return
    if len(candidates) > 1:
        args.only_project_ambiguous = sorted(candidates, key=lambda n: n.lower())
        return
    args.only_project_input = requested
    args.only_project_no_match = True


@dataclass
class RunContext:
    args: argparse.Namespace
    dt_from: datetime
    dt_to: datetime
    profiles: List[Dict[str, Any]]
    loaded_config_path: Optional[Path]
    worklog_path: Path
    source_strategy_effective: str


def build_run_context(
    *,
    config_path: str,
    date_from: Optional[str],
    date_to: Optional[str],
    options: Any,
    local_tz,
    repo_root: Path,
    as_run_options_fn: Callable[[Any], Any],
    get_date_range_fn: Callable[[Optional[str], Optional[str]], Tuple[datetime, datetime]],
    load_profiles_fn: Callable[[str, argparse.Namespace], Any],
    resolve_worklog_path_fn: Callable[[Optional[str], Optional[Path], Any, Path], Path],
    want_log_fn: Callable[[argparse.Namespace], bool],
) -> RunContext:
    run_options = as_run_options_fn(options)
    args = argparse.Namespace(**vars(run_options))
    args.projects_config = config_path
    args.date_from = date_from
    args.date_to = date_to

    if args.today:
        today_s = datetime.now(local_tz).strftime("%Y-%m-%d")
        args.date_from = today_s
        args.date_to = today_s
    elif args.yesterday:
        yest_s = (datetime.now(local_tz) - timedelta(days=1)).strftime("%Y-%m-%d")
        args.date_from = yest_s
        args.date_to = yest_s
    elif args.last_3_days:
        # Inclusive calendar days: "last 3 days" = today and the two prior days.
        now = datetime.now(local_tz)
        end_d = now.date()
        args.date_from = (end_d - timedelta(days=2)).isoformat()
        args.date_to = end_d.isoformat()
    elif args.last_week:
        now = datetime.now(local_tz)
        end_d = now.date()
        args.date_from = (end_d - timedelta(days=6)).isoformat()
        args.date_to = end_d.isoformat()
    elif args.last_14_days:
        now = datetime.now(local_tz)
        end_d = now.date()
        args.date_from = (end_d - timedelta(days=13)).isoformat()
        args.date_to = end_d.isoformat()
    elif args.last_month:
        now = datetime.now(local_tz)
        end_d = now.date()
        args.date_from = (end_d - timedelta(days=29)).isoformat()
        args.date_to = end_d.isoformat()

    dt_from, dt_to = get_date_range_fn(args.date_from, args.date_to)
    profiles, loaded_config_path, workspace = load_profiles_fn(args.projects_config, args)
    if loaded_config_path is None:
        # No project config exists yet; include uncategorized activity so first report is useful.
        args.include_uncategorized = True
        # Also show source summary by default for setup-free first runs, but not for machine-readable outputs.
        is_machine_readable = (
            getattr(args, 'machine_readable', False)
            or getattr(args, 'output_format', '') in ('json', 'ndjson', 'script')
            or (getattr(args, 'output_path', '') or '').endswith(('.json', '.ndjson'))
        )
        if not is_machine_readable:
            args.source_summary = True
    worklog_path = resolve_worklog_path_fn(
        args.worklog, loaded_config_path, workspace.get("worklog"), repo_root
    )
    _resolve_only_project_filter(args, profiles)
    chosen_strategy = str(getattr(args, "source_strategy", "auto") or "auto").strip().lower()
    if chosen_strategy not in {"auto", "worklog-first", "balanced"}:
        chosen_strategy = "auto"
    worklog_exists = worklog_path.exists() and worklog_path.is_file() and os.access(worklog_path, os.R_OK)
    if chosen_strategy == "balanced":
        source_strategy_effective = "balanced"
    elif chosen_strategy == "worklog-first":
        source_strategy_effective = "worklog-first" if worklog_exists else "balanced"
    else:
        source_strategy_effective = "worklog-first" if worklog_exists else "balanced"
    args.source_strategy = chosen_strategy
    args.source_strategy_effective = source_strategy_effective
    args.primary_source = worklog_path.name if source_strategy_effective == "worklog-first" else "balanced"
    noise_profile = str(getattr(args, "noise_profile", DEFAULT_NOISE_PROFILE) or DEFAULT_NOISE_PROFILE).strip().lower()
    if noise_profile not in NOISE_PROFILES:
        noise_profile = DEFAULT_NOISE_PROFILE
    args.noise_profile = noise_profile
    lovable_noise_profile = str(
        getattr(args, "lovable_noise_profile", DEFAULT_LOVABLE_NOISE_PROFILE) or DEFAULT_LOVABLE_NOISE_PROFILE
    ).strip().lower()
    if lovable_noise_profile not in LOVABLE_NOISE_PROFILES:
        lovable_noise_profile = DEFAULT_LOVABLE_NOISE_PROFILE
    args.lovable_noise_profile = lovable_noise_profile

    if want_log_fn(args):
        print(f"\nScanning: {dt_from.date()} -> {dt_to.date()}")
        if args.only_project:
            print(f"Only project: {args.only_project!r}")
        if getattr(args, "only_project_resolved", False) and getattr(args, "only_project_input", None):
            print(f"Project filter matched: {args.only_project_input!r} -> {args.only_project!r}")
        ambiguous_projects = getattr(args, "only_project_ambiguous", None) or []
        if ambiguous_projects:
            print(f"Project filter ambiguous: {args.only_project!r} matches {', '.join(ambiguous_projects)}")
        if getattr(args, "only_project_no_match", False):
            print(f"Project filter {args.only_project!r} matched no profiles")
        if args.customer:
            print(f"Only customer: {args.customer!r}")
        print(f"Local timezone: {local_tz}")
        print(f"Project profiles: {len(profiles)}")
        print(f"Worklog: {worklog_path}")
        if chosen_strategy == "worklog-first" and not worklog_exists:
            if worklog_path.exists() and worklog_path.is_file():
                print("Source strategy: worklog-first requested, but worklog not readable; using balanced fallback.")
            else:
                print("Source strategy: worklog-first requested, but worklog missing; using balanced fallback.")
        else:
            print(f"Source strategy: {source_strategy_effective} (requested: {chosen_strategy})")
        print(f"Noise profile: {noise_profile}")
        profile_hints = {
            "lenient": "keep almost all collector diagnostics/events",
            "strict": "filter common heartbeat/diagnostic noise",
            "ultra-strict": "aggressively filter diagnostics/repo churn noise",
        }
        print(f"Noise profile hint: {profile_hints.get(noise_profile, profile_hints['strict'])}")
        print(f"Lovable noise profile: {lovable_noise_profile}")
        print(
            f"Profile defaults: global={DEFAULT_NOISE_PROFILE}, lovable={DEFAULT_LOVABLE_NOISE_PROFILE}"
        )
        print()

    return RunContext(
        args=args,
        dt_from=dt_from,
        dt_to=dt_to,
        profiles=profiles,
        loaded_config_path=loaded_config_path,
        worklog_path=worklog_path,
        source_strategy_effective=source_strategy_effective,
    )


def collect_runtime_events(
    *,
    context: RunContext,
    home: Path,
    local_tz,
    chrome_epoch_delta_us: int,
    uncategorized: str,
    cursor_checkpoints_dir: Path,
    codex_ide_session_index: Path,
    worklog_source: str,
    cursor_checkpoints_source: str,
    classify_project_fn: Callable[[str, List[Dict[str, Any]]], str],
    make_event_fn: Callable[[str, Any, str, str], Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    runtime_collectors = RuntimeCollectors(
        cli_args=context.args,
        home=home,
        local_tz=local_tz,
        chrome_epoch_delta_us=chrome_epoch_delta_us,
        uncategorized=uncategorized,
        cursor_checkpoints_dir=cursor_checkpoints_dir,
        codex_ide_session_index=codex_ide_session_index,
        worklog_source=worklog_source,
        cursor_checkpoints_source=cursor_checkpoints_source,
        classify_project_fn=classify_project_fn,
        make_event_fn=make_event_fn,
        ai_logs_collector=ai_logs_collector,
        chrome_collector=chrome_collector,
        cursor_collector=cursor_collector,
        mail_collector=mail_collector,
        timelog_collector=timelog_collector,
        github_collector=github_collector,
        toggl_collector=toggl_collector,
        github_token=os.environ.get("GITHUB_TOKEN"),
    )
    return collect_all_events(
        context.profiles,
        context.dt_from,
        context.dt_to,
        context.args,
        context.worklog_path,
        home=home,
        chrome_history_path_fn=chrome_collector.chrome_history_path,
        detect_mail_root_fn=mail_collector.detect_mail_root,
        build_collector_specs_fn=build_collector_specs,
        collect_claude_code=runtime_collectors.collect_claude_code,
        collect_claude_desktop=runtime_collectors.collect_claude_desktop,
        collect_claude_ai_urls=runtime_collectors.collect_claude_ai_urls,
        collect_gemini_web_urls=runtime_collectors.collect_gemini_web_urls,
        collect_chrome=runtime_collectors.collect_chrome,
        collect_lovable_desktop=runtime_collectors.collect_lovable_desktop,
        collect_gemini_cli=runtime_collectors.collect_gemini_cli,
        collect_copilot_cli=runtime_collectors.collect_copilot_cli,
        collect_cursor=runtime_collectors.collect_cursor,
        collect_cursor_checkpoints=runtime_collectors.collect_cursor_checkpoints,
        collect_codex_ide=runtime_collectors.collect_codex_ide,
        collect_apple_mail=runtime_collectors.collect_apple_mail,
        collect_worklog=runtime_collectors.collect_worklog,
        collect_github=runtime_collectors.collect_github,
        collect_toggl=runtime_collectors.collect_toggl,
    )


def collect_screen_time_status(
    *,
    args: argparse.Namespace,
    dt_from: datetime,
    dt_to: datetime,
    collector_status: Dict[str, Dict[str, Any]],
    collect_screen_time_fn: Callable[[datetime, datetime], Any],
    want_log_fn: Callable[[argparse.Namespace], bool],
) -> Optional[Dict[str, float]]:
    screen_time_days = None
    if want_log_fn(args):
        print("Scanning Screen Time...")

    if args.screen_time == "off":
        collector_status["Screen Time"] = {
            "enabled": False,
            "reason": "disabled via --screen-time off",
            "days": 0,
        }
        return screen_time_days

    screen_time_days, screen_msg = collect_screen_time_fn(dt_from, dt_to)
    if screen_time_days is None:
        collector_status["Screen Time"] = {
            "enabled": args.screen_time == "on",
            "reason": screen_msg,
            "days": 0,
        }
        return screen_time_days

    collector_status["Screen Time"] = {
        "enabled": True,
        "reason": "",
        "days": len(screen_time_days),
    }
    return screen_time_days