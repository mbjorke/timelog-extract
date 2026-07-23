"""Typer commands: doctor, sources."""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from core.chromium_cache import CODEC_REINSTALL_HINT
from core.cli_app import app
from core.config import (
    load_profiles,
    projects_config_resolution_warnings,
    resolve_profile_worklog_paths,
    resolve_projects_config_path,
    resolve_worklog_path,
)
from core.doctor_cli_path import add_cli_path_rows
from core.doctor_collector_rows import add_collector_doctor_rows
from core.doctor_projects_config_rows import add_projects_config_lint_rows
from core.doctor_shadow_log_row import add_shadow_log_row
from core.doctor_source_rows import add_remote_api_doctor_rows, normalize_doctor_tri_state_mode
from core.doctor_table_checks import DoctorCheckStyle, doctor_check_file
from core.git_project_bootstrap import assess_config_git_coverage
from core.onboarding_guidance import (
    build_doctor_next_steps,
    print_next_steps,
    rule_hygiene_needed_for_config,
)
from core.workspace_root import runtime_workspace_root
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import (
    FAIL_ICON,
    NA_ICON,
    OK_ICON,
    STYLE_BORDER,
    STYLE_LABEL,
    STYLE_MUTED,
    WARN_ICON,
)

_DOCTOR_LOG = logging.getLogger(__name__)


@app.command()
def doctor(
    worklog: Annotated[
        Optional[str],
        typer.Option(
            "--worklog",
            help="Path to a worklog file (overrides config; recommended: per-project paths in timelog_projects.json).",
        ),
    ] = None,
    github_source: Annotated[
        str,
        typer.Option(
            "--github-source",
            help="GitHub source mode: auto, on, or off (doctor visibility only).",
        ),
    ] = "auto",
    github_user: Annotated[
        Optional[str],
        typer.Option(
            "--github-user",
            help="GitHub username(s) for public events; comma-separated for multiple (doctor visibility only).",
        ),
    ] = None,
    toggl_source: Annotated[
        str,
        typer.Option(
            "--toggl-source",
            help="Toggl source mode: auto, on, or off (doctor visibility only).",
        ),
    ] = "auto",
    jira_sync: Annotated[
        str,
        typer.Option(
            "--jira-sync",
            help="Jira sync mode: auto, on, or off (doctor visibility only).",
        ),
    ] = "auto",
):
    """
    Check source access and local integration health, then print a diagnostic table.
    
    Parameters:
        worklog (Optional[str]): Path to a worklog file that overrides the configured/workspace worklog.
        github_source (str): GitHub source mode: "auto", "on", or "off" (controls visibility of GitHub checks in the diagnostic output).
        github_user (Optional[str]): GitHub username(s), comma-separated for multiple, used when evaluating public event checks (visibility only).
        toggl_source (str): Toggl source mode: "auto", "on", or "off" (controls visibility of Toggl checks in the diagnostic output).
        jira_sync (str): Jira sync mode: "auto", "on", or "off" (controls visibility of Jira worklog sync checks in the diagnostic output).
    """
    from rich import box
    from rich.console import Console
    from rich.table import Table

    console = Console()
    gh_mode = normalize_doctor_tri_state_mode(github_source, "--github-source")
    jira_mode = normalize_doctor_tri_state_mode(jira_sync, "--jira-sync")
    print_command_hero(console, "doctor")
    console.print("")
    home = Path.home()
    # Sources disabled purely because their cache-evidence codec is missing.
    codec_blocked: list[str] = []
    workspace_root = runtime_workspace_root()
    projects_cfg = resolve_projects_config_path().expanduser()
    _profiles, loaded_config_path, workspace = load_profiles(
        str(projects_cfg),
        argparse.Namespace(project="default-project", keywords="", email=""),
    )
    workspace_worklog = workspace.get("worklog")
    worklog_path = resolve_worklog_path(
        worklog,
        loaded_config_path,
        workspace_worklog,
        workspace_root,
    )
    profile_worklogs = resolve_profile_worklog_paths(
        _profiles,
        config_path=loaded_config_path,
        script_dir=workspace_root,
    )

    table = Table(title="Gittan Health Check", box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = f"bold {STYLE_LABEL}"
    table.add_column("Source / Path", style=STYLE_LABEL)
    table.add_column("Status", justify="center")
    table.add_column("Details", style=STYLE_MUTED)

    check_style = DoctorCheckStyle(
        ok_icon=OK_ICON,
        warn_icon=WARN_ICON,
        fail_icon=FAIL_ICON,
        style_muted=STYLE_MUTED,
    )

    with console.status(f"[bold {STYLE_LABEL}]Running diagnostics..."):
        cli_on_path = add_cli_path_rows(table, home=home)
        project_config_ok = doctor_check_file(table, projects_cfg, "Project Config", check_style)
        for warning in projects_config_resolution_warnings(projects_cfg, profiles=_profiles):
            table.add_row(
                "Projects config",
                WARN_ICON,
                f"[{STYLE_MUTED}]{warning}[/{STYLE_MUTED}]",
            )
        add_projects_config_lint_rows(
            table,
            projects_cfg,
            warn_icon=WARN_ICON,
            style_muted=STYLE_MUTED,
        )
        add_shadow_log_row(
            table,
            projects_cfg,
            ok_icon=OK_ICON,
            warn_icon=WARN_ICON,
            style_muted=STYLE_MUTED,
            home=home,
        )
        # Check for shadow log capture errors (GH-408)
        capture_errors_file = home / ".gittan" / "capture-errors.jsonl"
        if capture_errors_file.exists():
            try:
                import json
                with capture_errors_file.open(encoding="utf-8") as f:
                    errors = [json.loads(line) for line in f if line.strip()]
                if errors:
                    latest_err = errors[-1]
                    table.add_row(
                        "Capture errors",
                        FAIL_ICON,
                        f"[{STYLE_MUTED}]Recent capture failure: {latest_err.get('error')} (last: {latest_err.get('timestamp')})[/{STYLE_MUTED}]",
                    )
            except Exception:
                pass
        using_single_worklog = bool(worklog) or bool(workspace_worklog)
        if using_single_worklog:
            if not worklog_path.exists():
                table.add_row("Worklog (Local)", FAIL_ICON, f"[{STYLE_MUTED}]Not found: {worklog_path}[/{STYLE_MUTED}]")
                worklog_ok = False
            elif not os.access(worklog_path, os.R_OK):
                table.add_row("Worklog (Local)", WARN_ICON, f"[{STYLE_MUTED}]No read permission: {worklog_path}[/{STYLE_MUTED}]")
                worklog_ok = False
            else:
                try:
                    from datetime import timezone
                    mtime = datetime.fromtimestamp(worklog_path.stat().st_mtime, timezone.utc)
                    age_days = (datetime.now(timezone.utc) - mtime).days
                    if age_days >= 7:
                        dt_str = mtime.date().isoformat()
                        table.add_row(
                            "Worklog (Local)",
                            WARN_ICON,
                            f"[{STYLE_MUTED}]Stale capture: no writes in last 7 days (last modified: {dt_str})[/{STYLE_MUTED}]",
                        )
                    else:
                        table.add_row("Worklog (Local)", OK_ICON, f"[{STYLE_MUTED}]Accessible[/{STYLE_MUTED}]")
                except OSError:
                    table.add_row("Worklog (Local)", OK_ICON, f"[{STYLE_MUTED}]Accessible[/{STYLE_MUTED}]")
                worklog_ok = True
        elif profile_worklogs:
            accessible = [path for path in profile_worklogs if path.exists() and os.access(path, os.R_OK)]
            total = len(profile_worklogs)
            readable = len(accessible)
            stale_paths = []
            for path in accessible:
                try:
                    from datetime import timezone
                    mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                    if (datetime.now(timezone.utc) - mtime).days >= 7:
                        stale_paths.append((path, mtime))
                except OSError:
                    continue

            if readable == total:
                if stale_paths:
                    oldest_date = min(stale_paths, key=lambda x: x[1])[1].date().isoformat()
                    table.add_row(
                        "Worklogs (Per-project)",
                        WARN_ICON,
                        f"[{STYLE_MUTED}]Per-project worklogs configured ({readable}/{total} accessible) — "
                        f"Stale capture: {len(stale_paths)} worklog(s) have no writes in last 7 days (oldest: {oldest_date})[/{STYLE_MUTED}]",
                    )
                else:
                    table.add_row(
                        "Worklogs (Per-project)",
                        OK_ICON,
                        f"[{STYLE_MUTED}]Per-project worklogs configured ({readable}/{total} accessible)[/{STYLE_MUTED}]",
                    )
                worklog_ok = True
            elif readable > 0:
                if stale_paths:
                    oldest_date = min(stale_paths, key=lambda x: x[1])[1].date().isoformat()
                    table.add_row(
                        "Worklogs (Per-project)",
                        WARN_ICON,
                        f"[{STYLE_MUTED}]Per-project worklogs configured ({readable}/{total} accessible) — "
                        f"Stale capture: {len(stale_paths)} worklog(s) have no writes in last 7 days (oldest: {oldest_date})[/{STYLE_MUTED}]",
                    )
                else:
                    table.add_row(
                        "Worklogs (Per-project)",
                        WARN_ICON,
                        f"[{STYLE_MUTED}]Per-project worklogs configured ({readable}/{total} accessible)[/{STYLE_MUTED}]",
                    )
                worklog_ok = True
            else:
                table.add_row(
                    "Worklogs (Per-project)",
                    WARN_ICON,
                    f"[{STYLE_MUTED}]Per-project worklogs configured (0/{total} accessible)[/{STYLE_MUTED}]",
                )
                worklog_ok = False
        else:
            if not worklog_path.exists():
                table.add_row("Worklog (Local)", FAIL_ICON, f"[{STYLE_MUTED}]Not found: {worklog_path}[/{STYLE_MUTED}]")
                worklog_ok = False
            elif not os.access(worklog_path, os.R_OK):
                table.add_row("Worklog (Local)", WARN_ICON, f"[{STYLE_MUTED}]No read permission: {worklog_path}[/{STYLE_MUTED}]")
                worklog_ok = False
            else:
                try:
                    from datetime import timezone
                    mtime = datetime.fromtimestamp(worklog_path.stat().st_mtime, timezone.utc)
                    age_days = (datetime.now(timezone.utc) - mtime).days
                    if age_days >= 7:
                        dt_str = mtime.date().isoformat()
                        table.add_row(
                            "Worklog (Local)",
                            WARN_ICON,
                            f"[{STYLE_MUTED}]Stale capture: no writes in last 7 days (last modified: {dt_str})[/{STYLE_MUTED}]",
                        )
                    else:
                        table.add_row("Worklog (Local)", OK_ICON, f"[{STYLE_MUTED}]Accessible[/{STYLE_MUTED}]")
                except OSError:
                    table.add_row("Worklog (Local)", OK_ICON, f"[{STYLE_MUTED}]Accessible[/{STYLE_MUTED}]")
                worklog_ok = True
        coverage = assess_config_git_coverage(_profiles)
        coverage_icon = OK_ICON if coverage.status == "ok" else WARN_ICON if coverage.status == "warn" else NA_ICON
        coverage_detail = coverage.detail
        if coverage.status == "warn" and coverage.suggested_terms:
            coverage_detail = f"{coverage.detail} Suggested cues: {', '.join(coverage.suggested_terms)}"
        table.add_row("Git match_terms coverage", coverage_icon, f"[{STYLE_MUTED}]{coverage_detail}[/{STYLE_MUTED}]")

        from collectors.git_commits import configured_git_repo_paths

        git_repos = configured_git_repo_paths(_profiles)
        if not git_repos:
            table.add_row(
                "Git commits",
                NA_ICON,
                f"[{STYLE_MUTED}]No profile has git_repo configured (--git column)[/{STYLE_MUTED}]",
            )
        else:
            missing_repos = [p for p in git_repos if not p.exists()]
            if missing_repos:
                table.add_row(
                    "Git commits",
                    FAIL_ICON,
                    f"[{STYLE_MUTED}]git_repo path not found ({missing_repos[0].name})[/{STYLE_MUTED}]",
                )
            else:
                table.add_row(
                    "Git commits",
                    OK_ICON,
                    f"[{STYLE_MUTED}]{len(git_repos)} repo(s); pass --git on report for Git-only hours[/{STYLE_MUTED}]",
                )

        from core.sqlite_backup import sqlite_db_check_detail
        from core.timely_memory import detect_timely_memory_db, timely_memory_db_candidates

        memory_db = detect_timely_memory_db(timely_memory_db_candidates(home))
        if memory_db:
            table.add_row(
                "Timely Memory (presence)",
                OK_ICON,
                f"[{STYLE_MUTED}]{sqlite_db_check_detail(memory_db, 'Local buffer readable')}; "
                f"opt-in via --timely-memory-source on (read-only, timestamps only)[/{STYLE_MUTED}]",
            )
        else:
            table.add_row(
                "Timely Memory (presence)",
                NA_ICON,
                f"[{STYLE_MUTED}]No local Memory buffer found (source stays off; opt-in only)[/{STYLE_MUTED}]",
            )

        add_collector_doctor_rows(
            table,
            home,
            check_style,
            codec_blocked=codec_blocked,
            ok_icon=OK_ICON,
            warn_icon=WARN_ICON,
            fail_icon=FAIL_ICON,
            na_icon=NA_ICON,
            style_muted=STYLE_MUTED,
        )

        # Liveness (GH-366): "Logs readable" proves reachability only; these
        # rows show when each source last produced evidence. Advisory only —
        # never let them break the rest of the diagnostic table.
        try:
            from core.doctor_liveness_rows import add_source_liveness_rows

            add_source_liveness_rows(
                table,
                home=home,
                ok_icon=OK_ICON,
                warn_icon=WARN_ICON,
                na_icon=NA_ICON,
                style_muted=STYLE_MUTED,
            )
        except Exception:  # noqa: BLE001 - liveness rows are advisory, never fatal
            _DOCTOR_LOG.debug("source liveness rows skipped", exc_info=True)

        add_remote_api_doctor_rows(
            table,
            gh_mode=gh_mode,
            github_user=github_user,
            toggl_source=toggl_source,
            jira_sync=jira_mode,
        )
    console.print(table)
    if codec_blocked:
        console.print(
            f"\n{WARN_ICON} [bold]Evidence codecs missing[/bold] — "
            f"{', '.join(codec_blocked)} disabled or degraded, so AI-session hours "
            f"are silently under-counted."
        )
        console.print(
            f"  [{STYLE_MUTED}]Fix: {CODEC_REINSTALL_HINT}[/{STYLE_MUTED}]"
        )
    console.print(
        f"\n[{STYLE_MUTED}]Note: warnings/errors for Mail/Chrome/Screen Time often mean Full Disk Access is required "
        f"for your Terminal in System Settings > Privacy & Security.[/{STYLE_MUTED}]\n"
    )
    config_valid = project_config_ok and loaded_config_path is not None
    print_next_steps(
        console,
        build_doctor_next_steps(
            cli_on_path=cli_on_path,
            projects_config_ok=project_config_ok,
            config_valid=config_valid,
            worklog_ok=worklog_ok,
            match_terms_ok=coverage.status != "warn",
            rule_hygiene_needed=rule_hygiene_needed_for_config(
                projects_cfg, git_coverage_warn=coverage.status == "warn"
            ),
            config_path=projects_cfg,
            worklog_path=worklog_path,
        ),
    )
    console.print(
        f"[{STYLE_MUTED}]Hint: For large Screen Time deltas, run "
        f"`gittan evidence-check --from YYYY-MM-DD --to YYYY-MM-DD` for the exact day range.[/{STYLE_MUTED}]"
    )


