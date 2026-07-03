"""Runtime orchestration helpers for report service boundaries."""

from __future__ import annotations

import argparse
import atexit
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from collectors import (
    ai_logs as ai_logs_collector,
    antigravity as antigravity_collector,
    chrome as chrome_collector,
    conductor as conductor_collector,
    cursor as cursor_collector,
    github as github_collector,
    mail as mail_collector,
    timelog as timelog_collector,
    toggl as toggl_collector,
    windsurf as windsurf_collector,
    zed as zed_collector,
)
from core.collector_registry import build_collector_specs
from core.config import resolve_profile_worklog_paths
from core.noise_profiles import (
    DEFAULT_LOVABLE_NOISE_PROFILE,
    DEFAULT_NOISE_PROFILE,
    LOVABLE_NOISE_PROFILES,
    NOISE_PROFILES,
)
from core.pipeline import collect_all_events
from core.runtime_collectors import RuntimeCollectors


def _resolve_only_project_filter(args: argparse.Namespace, profiles: List[Dict[str, Any]]) -> None:
    requested = str(getattr(args, "only_project", "") or "").strip()
    if not requested:
        return
    by_name = {
        str(p.get("name", "")).strip().lower(): str(p.get("name", "")).strip()
        for p in profiles
        if str(p.get("name", "")).strip()
    }
    exact = by_name.get(requested.lower())
    if exact:
        if exact != requested:
            args.only_project_input = requested
            args.only_project_resolved = True
        args.only_project = exact
        return

    candidates: list[str] = []
    seen: set[str] = set()
    needle = requested.lower()
    for profile in profiles:
        canonical = str(profile.get("name", "")).strip()
        if not canonical:
            continue
        names = [canonical] + [
            str(a).strip() for a in (profile.get("aliases") or []) if str(a).strip()
        ]
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
    worklog_paths: List[Path]
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
            getattr(args, "machine_readable", False)
            or getattr(args, "output_format", "") in ("json", "ndjson", "script")
            or (getattr(args, "output_path", "") or "").endswith((".json", ".ndjson"))
        )
        if not is_machine_readable:
            args.source_summary = True
    workspace_worklog = workspace.get("worklog")
    profile_worklog_paths = resolve_profile_worklog_paths(
        profiles,
        config_path=loaded_config_path,
        script_dir=repo_root,
    )
    attribution_mode = str(getattr(args, "attribution_mode", "") or "").strip().lower()
    if attribution_mode == "commit-first":
        # Approximate "commit-first / my-activity-only" comparisons with the least invasive
        # set of existing CLI knobs:
        # - enable GitHub public-event collection
        # - disable passive sources (mail/chrome/screen-time)
        # - inject an explicit empty worklog so worklog-based/project worklogs are not used
        args.github_source = "on"
        args.source_strategy = "balanced"
        args.mail_source = "off"
        args.chrome_source = "off"
        args.screen_time = "off"
        if args.worklog is None:
            with tempfile.NamedTemporaryFile(
                prefix="gittan-commit-first-",
                suffix=".md",
                delete=False,
            ) as tf:
                tf.write(b"")
                tf.flush()
                empty_worklog_path = tf.name
            args.worklog = empty_worklog_path

            def _unlink_commit_first_worklog() -> None:
                try:
                    os.unlink(empty_worklog_path)
                except OSError:
                    pass

            atexit.register(_unlink_commit_first_worklog)
    args.attribution_mode = attribution_mode or None

    has_explicit_base_worklog = args.worklog is not None or bool(workspace_worklog)

    # In per-project mode (profile worklogs configured without an explicit base),
    # do not implicitly inject legacy repo TIMELOG.md into the active worklog set.
    if profile_worklog_paths and not has_explicit_base_worklog:
        worklog_paths = list(profile_worklog_paths)
        worklog_path = worklog_paths[0]
        has_implicit_base_worklog = False
    else:
        worklog_path = resolve_worklog_path_fn(
            args.worklog, loaded_config_path, workspace_worklog, repo_root
        )
        worklog_paths = [worklog_path]
        has_implicit_base_worklog = True
        # Preserve explicit --worklog override behavior as a single authoritative path.
        if args.worklog is None:
            for candidate in profile_worklog_paths:
                if candidate not in worklog_paths:
                    worklog_paths.append(candidate)
    args.worklog_paths = [str(path) for path in worklog_paths]
    _resolve_only_project_filter(args, profiles)
    chosen_strategy = str(getattr(args, "source_strategy", "auto") or "auto").strip().lower()
    if chosen_strategy not in {"auto", "worklog-first", "balanced"}:
        chosen_strategy = "auto"
    worklog_exists = (
        worklog_path.exists() and worklog_path.is_file() and os.access(worklog_path, os.R_OK)
    )
    if chosen_strategy == "balanced":
        source_strategy_effective = "balanced"
    elif chosen_strategy == "worklog-first":
        source_strategy_effective = "worklog-first" if worklog_exists else "balanced"
    else:
        source_strategy_effective = "worklog-first" if worklog_exists else "balanced"
    args.source_strategy = chosen_strategy
    args.source_strategy_effective = source_strategy_effective
    args.primary_source = (
        worklog_path.name if source_strategy_effective == "worklog-first" else "balanced"
    )
    noise_profile = (
        str(getattr(args, "noise_profile", DEFAULT_NOISE_PROFILE) or DEFAULT_NOISE_PROFILE)
        .strip()
        .lower()
    )
    if noise_profile not in NOISE_PROFILES:
        noise_profile = DEFAULT_NOISE_PROFILE
    args.noise_profile = noise_profile
    lovable_noise_profile = (
        str(
            getattr(args, "lovable_noise_profile", DEFAULT_LOVABLE_NOISE_PROFILE)
            or DEFAULT_LOVABLE_NOISE_PROFILE
        )
        .strip()
        .lower()
    )
    if lovable_noise_profile not in LOVABLE_NOISE_PROFILES:
        lovable_noise_profile = DEFAULT_LOVABLE_NOISE_PROFILE
    args.lovable_noise_profile = lovable_noise_profile

    if want_log_fn(args):
        print(f"\nScanning: {dt_from.date()} -> {dt_to.date()}")
        if args.only_project:
            print(f"Only project: {args.only_project!r}")
        if getattr(args, "only_project_resolved", False) and getattr(
            args, "only_project_input", None
        ):
            print(f"Project filter matched: {args.only_project_input!r} -> {args.only_project!r}")
        ambiguous_projects = getattr(args, "only_project_ambiguous", None) or []
        if ambiguous_projects:
            print(
                f"Project filter ambiguous: {args.only_project!r} matches {', '.join(ambiguous_projects)}"
            )
        if getattr(args, "only_project_no_match", False):
            print(f"Project filter {args.only_project!r} matched no profiles")
        if args.customer:
            print(f"Only customer: {args.customer!r}")
        print(f"Local timezone: {local_tz}")
        print(f"Project profiles: {len(profiles)}")
        from core.config import projects_config_resolution_warnings

        active_config_path = Path(args.projects_config).expanduser().resolve()
        for warning in projects_config_resolution_warnings(
            active_config_path,
            cwd=Path.cwd(),
            profiles=profiles,
        ):
            print(f"[Warning] {warning}")
        if has_implicit_base_worklog:
            print(f"Worklog: {worklog_path}")
        else:
            print(f"Worklogs: {len(worklog_paths)} per-project paths")
        if has_implicit_base_worklog and len(worklog_paths) > 1:
            print(f"Per-project worklogs: {len(worklog_paths) - 1} additional paths")
        if chosen_strategy == "worklog-first" and not worklog_exists:
            if worklog_path.exists() and worklog_path.is_file():
                print(
                    "Source strategy: worklog-first requested, but worklog not readable; using balanced fallback."
                )
            else:
                print(
                    "Source strategy: worklog-first requested, but worklog missing; using balanced fallback."
                )
        else:
            print(f"Source strategy: {source_strategy_effective} (requested: {chosen_strategy})")
        print(f"Noise profile: {noise_profile}")
        if attribution_mode == "commit-first":
            print("Attribution mode: commit-first (GitHub-focused comparison preset)")
            print(
                "Preset sources: github=on, chrome=off, mail=off, screen_time=off, source_strategy=balanced"
            )
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
        invoice_mode = str(getattr(args, "invoice_mode", "baseline") or "baseline").strip().lower()
        invoice_truth = str(getattr(args, "invoice_ground_truth", "") or "").strip()
        if invoice_mode != "baseline":
            print(f"Invoice mode: {invoice_mode}")
            if invoice_truth:
                print(f"Invoice ground truth: {invoice_truth}")
        print()

    return RunContext(
        args=args,
        dt_from=dt_from,
        dt_to=dt_to,
        profiles=profiles,
        loaded_config_path=loaded_config_path,
        worklog_path=worklog_path,
        worklog_paths=worklog_paths,
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
        antigravity_collector=antigravity_collector,
        windsurf_collector=windsurf_collector,
        mail_collector=mail_collector,
        timelog_collector=timelog_collector,
        github_collector=github_collector,
        toggl_collector=toggl_collector,
        zed_collector=zed_collector,
        conductor_collector=conductor_collector,
        github_token=os.environ.get("GITHUB_TOKEN"),
    )
    return collect_all_events(
        context.profiles,
        context.dt_from,
        context.dt_to,
        context.args,
        context.worklog_paths,
        home=home,
        chrome_history_path_fn=chrome_collector.chrome_history_paths,
        detect_mail_root_fn=mail_collector.detect_mail_root,
        build_collector_specs_fn=build_collector_specs,
        collect_claude_code=runtime_collectors.collect_claude_code,
        collect_claude_desktop=runtime_collectors.collect_claude_desktop,
        collect_claude_desktop_code=runtime_collectors.collect_claude_desktop_code,
        collect_claude_ai_urls=runtime_collectors.collect_claude_ai_urls,
        collect_gemini_web_urls=runtime_collectors.collect_gemini_web_urls,
        collect_chrome=runtime_collectors.collect_chrome,
        collect_lovable_desktop=runtime_collectors.collect_lovable_desktop,
        collect_gemini_cli=runtime_collectors.collect_gemini_cli,
        collect_copilot_cli=runtime_collectors.collect_copilot_cli,
        collect_cursor=runtime_collectors.collect_cursor,
        collect_antigravity=runtime_collectors.collect_antigravity,
        collect_windsurf=runtime_collectors.collect_windsurf,
        collect_cursor_checkpoints=runtime_collectors.collect_cursor_checkpoints,
        collect_codex_ide=runtime_collectors.collect_codex_ide,
        collect_apple_mail=runtime_collectors.collect_apple_mail,
        collect_worklog=runtime_collectors.collect_worklog,
        collect_github=runtime_collectors.collect_github,
        collect_toggl=runtime_collectors.collect_toggl,
        collect_calendar=runtime_collectors.collect_calendar,
        collect_zed=runtime_collectors.collect_zed,
        collect_conductor=runtime_collectors.collect_conductor,
        calendar_has_selection=bool(runtime_collectors.calendar_roles()),
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


def collect_timely_memory_status(
    *,
    args: argparse.Namespace,
    dt_from: datetime,
    dt_to: datetime,
    collector_status: Dict[str, Dict[str, Any]],
    collect_timely_memory_fn: Callable[[datetime, datetime], Any],
) -> Optional[Dict[str, float]]:
    """Opt-in presence comparator (coverage_comparator role, like Screen Time).

    Off by default: nothing is read unless --timely-memory-source on. The
    returned per-day presence seconds are context only — they never enter the
    event pipeline, so they cannot create classified project time.
    """
    from collectors.timely_memory import TIMELY_MEMORY_SOURCE, timely_memory_source_enabled

    enabled, reason = timely_memory_source_enabled(args)
    if not enabled:
        collector_status[TIMELY_MEMORY_SOURCE] = {
            "enabled": False,
            "reason": reason,
            "days": 0,
        }
        return None

    memory_days, memory_msg = collect_timely_memory_fn(dt_from, dt_to)
    if memory_days is None:
        collector_status[TIMELY_MEMORY_SOURCE] = {
            "enabled": True,
            "reason": memory_msg,
            "days": 0,
        }
        return None

    collector_status[TIMELY_MEMORY_SOURCE] = {
        "enabled": True,
        "reason": "",
        "days": len(memory_days),
        "presence_hours": round(sum(memory_days.values()) / 3600.0, 2),
    }
    return memory_days
