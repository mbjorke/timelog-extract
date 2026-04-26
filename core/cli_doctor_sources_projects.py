"""Typer commands: doctor, sources."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import site
import sqlite3
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import typer
from typing import Annotated, Optional

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.cli_prompts import prompt_for_timeframe
from core.config import load_profiles, resolve_projects_config_path, resolve_worklog_path
from core.git_project_bootstrap import assess_match_terms_coverage
from core.onboarding_guidance import build_doctor_next_steps, print_next_steps
from core.doctor_cli_path import add_cli_path_rows
from core.doctor_source_rows import add_github_doctor_row, add_toggl_doctor_row
from collectors.lovable_desktop import lovable_desktop_history_candidates
from core.doctor_copilot_cli_row import add_copilot_cli_doctor_row
from core.workspace_root import runtime_workspace_root
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import FAIL_ICON, NA_ICON, OK_ICON, STYLE_BORDER, STYLE_LABEL, STYLE_MUTED, WARN_ICON

_DOCTOR_LOG = logging.getLogger(__name__)
@app.command()
def doctor(
    worklog: Annotated[
        Optional[str],
        typer.Option(
            "--worklog",
            help="Path to TIMELOG.md (overrides config; default matches report: config worklog, else project default).",
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
            help="GitHub username for public events (doctor visibility only).",
        ),
    ] = None,
    toggl_source: Annotated[
        str,
        typer.Option(
            "--toggl-source",
            help="Toggl source mode: auto, on, or off (doctor visibility only).",
        ),
    ] = "auto",
):
    """
    Check source access and local integration health, then print a diagnostic table.
    
    Parameters:
        worklog (Optional[str]): Path to TIMELOG.md that overrides the configured/workspace worklog.
        github_source (str): GitHub source mode: "auto", "on", or "off" (controls visibility of GitHub checks in the diagnostic output).
        github_user (Optional[str]): GitHub username to use when evaluating public event checks (visibility only).
        toggl_source (str): Toggl source mode: "auto", "on", or "off" (controls visibility of Toggl checks in the diagnostic output).
    """
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    gh_mode = (github_source or "auto").strip().lower()
    if gh_mode not in {"auto", "on", "off"}:
        raise typer.BadParameter("Expected one of: auto, on, off", param_hint="--github-source")
    print_command_hero(console, "doctor")
    console.print("")
    home = Path.home()
    workspace_root = runtime_workspace_root()
    projects_cfg = resolve_projects_config_path().expanduser()
    _profiles, loaded_config_path, workspace = load_profiles(
        str(projects_cfg),
        argparse.Namespace(project="default-project", keywords="", email=""),
    )
    worklog_path = resolve_worklog_path(
        worklog,
        loaded_config_path,
        workspace.get("worklog"),
        workspace_root,
    )

    table = Table(title="Gittan Health Check", box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = f"bold {STYLE_LABEL}"
    table.add_column("Source / Path", style=STYLE_LABEL)
    table.add_column("Status", justify="center")
    table.add_column("Details", style=STYLE_MUTED)

    def check_file(path: Path, label: str):
        if not path.exists():
            table.add_row(label, FAIL_ICON, f"[{STYLE_MUTED}]Not found: {path}[/{STYLE_MUTED}]")
            return False
        if not os.access(path, os.R_OK):
            table.add_row(label, WARN_ICON, f"[{STYLE_MUTED}]No read permission: {path}[/{STYLE_MUTED}]")
            return False
        table.add_row(label, OK_ICON, f"[{STYLE_MUTED}]Accessible[/{STYLE_MUTED}]")
        return True

    def check_db(path: Path, label: str, table_name: str):
        if not path.exists():
            table.add_row(label, FAIL_ICON, f"[{STYLE_MUTED}]DB not found[/{STYLE_MUTED}]")
            return False

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            shutil.copy2(path, tmp.name)
            conn = sqlite3.connect(tmp.name)
            c = conn.cursor()
            c.execute(f"SELECT count(*) FROM {table_name} LIMIT 1")
            c.fetchone()
            conn.close()
            table.add_row(label, OK_ICON, f"[{STYLE_MUTED}]DB query successful[/{STYLE_MUTED}]")
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                table.add_row(label, WARN_ICON, f"[{STYLE_MUTED}]DB locked (try closing app)[/{STYLE_MUTED}]")
            else:
                table.add_row(label, FAIL_ICON, f"[{STYLE_MUTED}]Query failed: {e}[/{STYLE_MUTED}]")
            return False
        except PermissionError:
            table.add_row(label, FAIL_ICON, f"[{STYLE_MUTED}]Full Disk Access required[/{STYLE_MUTED}]")
            return False
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    with console.status(f"[bold {STYLE_LABEL}]Running diagnostics..."):
        cli_on_path = add_cli_path_rows(table, home=home)
        project_config_ok = check_file(projects_cfg, "Project Config")
        worklog_ok = check_file(worklog_path, "Worklog (Local)")
        coverage = assess_match_terms_coverage(Path.cwd(), _profiles)
        coverage_icon = OK_ICON if coverage.status == "ok" else WARN_ICON if coverage.status == "warn" else NA_ICON
        coverage_detail = coverage.detail
        if coverage.status == "warn" and coverage.suggested_terms:
            coverage_detail = f"{coverage.detail} Suggested cues: {', '.join(coverage.suggested_terms)}"
        table.add_row("Git match_terms coverage", coverage_icon, f"[{STYLE_MUTED}]{coverage_detail}[/{STYLE_MUTED}]")

        chrome_path = home / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
        check_db(chrome_path, "Chrome History", "urls")
        lh = lovable_desktop_history_candidates(home)
        if lh:
            check_db(lh[0], "Lovable Desktop History", "urls")
        else:
            table.add_row(
                "Lovable Desktop History",
                NA_ICON,
                f"[{STYLE_MUTED}]No History DB yet (browse in Lovable to create one)[/{STYLE_MUTED}]",
            )

        mail_path = home / "Library" / "Mail"
        if mail_path.exists():
            try:
                list(mail_path.glob("V[0-9]*"))
                table.add_row("Apple Mail", OK_ICON, f"[{STYLE_MUTED}]Folder accessible[/{STYLE_MUTED}]")
            except PermissionError:
                table.add_row("Apple Mail", FAIL_ICON, f"[{STYLE_MUTED}]Permission denied (Full Disk Access?)[/{STYLE_MUTED}]")
        else:
            table.add_row("Apple Mail", NA_ICON, f"[{STYLE_MUTED}]Path not found[/{STYLE_MUTED}]")

        cursor_log_path = (
            home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "storage.json"
        )
        check_file(cursor_log_path, "Cursor Storage")

        cursor_checkpoints = (
            home / "Library/Application Support/Cursor/User/globalStorage/anysphere.cursor-commits/checkpoints"
        )
        if cursor_checkpoints.exists():
            table.add_row("Cursor Checkpoints", OK_ICON, f"[{STYLE_MUTED}]Folder accessible[/{STYLE_MUTED}]")
        else:
            table.add_row("Cursor Checkpoints", NA_ICON, f"[{STYLE_MUTED}]Not found[/{STYLE_MUTED}]")

        st_path = home / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db"
        if not st_path.exists():
            st_path = home / "Library" / "Application Support" / "KnowledgeC" / "knowledgeC.db"
        check_db(st_path, "Screen Time DB", "ZOBJECT")

        claude_path = home / ".claude" / "projects"
        if claude_path.exists():
            table.add_row("Claude Code CLI", OK_ICON, f"[{STYLE_MUTED}]Found projects[/{STYLE_MUTED}]")
        else:
            table.add_row("Claude Code CLI", NA_ICON, f"[{STYLE_MUTED}]Path not found[/{STYLE_MUTED}]")

        add_copilot_cli_doctor_row(
            table,
            home,
            ok_icon=OK_ICON,
            warn_icon=WARN_ICON,
            na_icon=NA_ICON,
            style_muted=STYLE_MUTED,
        )

        add_github_doctor_row(table, gh_mode, github_user)
        add_toggl_doctor_row(table, toggl_source)
    console.print(table)
    console.print(
        "\n[#8f86ad]Note: warnings/errors for Mail/Chrome/Screen Time often mean Full Disk Access is required "
        "for your Terminal in System Settings > Privacy & Security.[/#8f86ad]\n"
    )
    print_next_steps(
        console,
        build_doctor_next_steps(
            cli_on_path=cli_on_path,
            projects_config_ok=project_config_ok,
            worklog_ok=worklog_ok,
            match_terms_ok=coverage.status != "warn",
            config_path=projects_cfg,
            worklog_path=worklog_path,
        ),
    )


@app.command()
def sources():
    """Analyze which data sources are contributing the most to your reports."""
    from core.analytics import estimate_hours_by_day, group_by_day
    from core.domain import session_duration_hours
    from core.report_service import LOCAL_TZ, _compute_sessions, _session_duration_hours, run_timelog_report
    from core.sources import AI_SOURCES
    from rich.console import Console
    from rich.table import Table
    from rich import box

    picked = prompt_for_timeframe()

    options = TimelogRunOptions(
        date_from=picked.get("date_from"),
        date_to=picked.get("date_to"),
        today=picked.get("today", False),
        yesterday=picked.get("yesterday", False),
        last_3_days=picked.get("last_3_days", False),
        last_week=picked.get("last_week", False),
        last_14_days=picked.get("last_14_days", False),
        last_month=picked.get("last_month", False),
        projects_config=default_projects_config_option(),
        quiet=True,
    )

    console = Console()
    with console.status("[bold blue]Analyzing source importance..."):
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)

    if not report.all_events:
        console.print("[yellow]No data found for this period to analyze.[/yellow]")
        return

    source_counts = defaultdict(int)
    source_hours = defaultdict(float)

    for event in report.all_events:
        source_counts[event["source"]] += 1

    raw_grouped = group_by_day(report.all_events, local_tz=LOCAL_TZ)
    raw_overall = estimate_hours_by_day(
        raw_grouped,
        gap_minutes=15,
        min_session_minutes=15,
        min_session_passive_minutes=5,
        compute_sessions_fn=_compute_sessions,
        session_duration_hours_fn=_session_duration_hours,
    )

    uncategorized_count = defaultdict(int)
    uncategorized_samples = defaultdict(list)
    for day_data in raw_overall.values():
        for start, end, session_events in day_data["sessions"]:
            dur = session_duration_hours(session_events, start, end, 15, 5, AI_SOURCES)

            session_counts = defaultdict(int)
            for e in session_events:
                if e.get("project") == "Uncategorized":
                    src = e["source"]
                    uncategorized_count[src] += 1
                    detail = e.get("detail", "")
                    if detail and detail not in uncategorized_samples[src] and len(uncategorized_samples[src]) < 3:
                        uncategorized_samples[src].append(detail)
                session_counts[e["source"]] += 1

            total_session_events = len(session_events)
            if total_session_events > 0:
                for src, count in session_counts.items():
                    share = dur * (count / total_session_events)
                    source_hours[src] += share

    table = Table(
        title=f"Source Importance Analysis ({options.date_from} to {options.date_to})",
        box=box.ROUNDED,
    )
    table.add_column("Source", style="cyan")
    table.add_column("Events", justify="right", style="green")
    table.add_column("Uncat.", justify="right", style="red")
    table.add_column("Samples (Uncat)", style="dim", max_width=40)
    table.add_column("Est. Hours Impact", justify="right", style="magenta")
    table.add_column("Weight %", justify="right", style="dim")

    total_impact_h = sum(source_hours.values())
    sorted_sources = sorted(source_counts.keys(), key=lambda s: source_hours[s], reverse=True)

    for src in sorted_sources:
        pct = (source_hours[src] / total_impact_h * 100) if total_impact_h > 0 else 0
        samples_text = " | ".join(uncategorized_samples[src])
        table.add_row(
            src,
            str(source_counts[src]),
            str(uncategorized_count[src]),
            samples_text,
            f"{source_hours[src]:.1f}h",
            f"{pct:.1f}%",
        )

    console.print(table)
    console.print(
        "\n[dim]Note: 'Est. Hours Impact' represents how much of your total session time is 'backed' by this "
        "specific source.[/dim]\n"
    )
