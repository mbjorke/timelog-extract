"""gittan cast — record a real status + doctor session as a semantic .cast file.

Output format: asciicast v3 with Gittan 'g' events (see outputs/cast_writer.py).
Rendered by the Gittan player (gittan-player-sketch.html and future embed).
Playable in fallback by standard `asciinema play` via paired 'o' events.

Usage:
    gittan cast --out demo.cast --last-14-days
    gittan cast --out demo.cast --today
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from core.cli_app import app
from core.config import default_projects_config_option
from core.workspace_root import runtime_workspace_root
from outputs.cast_writer import CastWriter


@app.command("cast")
def cast_cmd(
    out: Annotated[Path, typer.Option("--out", help=".cast output path")] = Path("demo.cast"),
    last_14_days: Annotated[bool, typer.Option("--last-14-days", help="Status timeframe: last 14 days (default)")] = False,
    today: Annotated[bool, typer.Option("--today", help="Status timeframe: today only")] = False,
    last_week: Annotated[bool, typer.Option("--last-week", help="Status timeframe: last 7 days")] = False,
    projects_config: Annotated[str, typer.Option(hidden=True)] = default_projects_config_option(),
    title: Annotated[str, typer.Option("--title", help="Session title embedded in the .cast header")] = "gittan demo",
) -> None:
    """Record a gittan status + doctor session as a structured semantic .cast file."""
    w = CastWriter(out, title=title)
    _record_status(w, today=today, last_week=last_week, last_14_days=last_14_days, projects_config=projects_config)
    w.blank()
    _record_doctor(w)
    saved = w.save()
    typer.echo(f"✓ {saved}  ({w.event_count} semantic events)")


# ── Status section ─────────────────────────────────────────────────────────────

def _record_status(
    w: CastWriter,
    *,
    today: bool,
    last_week: bool,
    last_14_days: bool,
    projects_config: str,
) -> None:
    from core.report_service import run_timelog_report

    # Default to last-14-days when no flag given
    use_14 = last_14_days or (not today and not last_week)

    now = datetime.now()
    if today:
        date_from = date_to = now.strftime("%Y-%m-%d")
        timeframe_str = date_from
        cmd_flag = "--today"
    elif last_week:
        date_to = now.strftime("%Y-%m-%d")
        date_from = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        timeframe_str = f"{date_from} to {date_to}"
        cmd_flag = "--last-week"
    else:
        date_to = now.strftime("%Y-%m-%d")
        date_from = (now - timedelta(days=14)).strftime("%Y-%m-%d")
        timeframe_str = f"{date_from} to {date_to}"
        cmd_flag = "--last-14-days"

    w.prompt(f"gittan status {cmd_flag}")
    w.bee_box("Gittan Status", [
        "Local traces become review-ready evidence.",
        "Use --additive when project totals must reconcile.",
        "Estimates stay local until you approve them.",
    ])
    w.status_line("observed → classified → approved")
    w.heading(f"Gittan Status — {timeframe_str}")

    try:
        from core.cli_options import TimelogRunOptions
        options = TimelogRunOptions(
            projects_config=projects_config,
            date_from=date_from,
            date_to=date_to,
            today=today,
            yesterday=False,
            last_3_days=False,
            last_week=last_week,
            last_14_days=use_14,
            last_month=False,
            quiet=True,
        )
        report = run_timelog_report(projects_config, date_from, date_to, options)

        if not report.included_events:
            w.note("No local evidence found for this period. Run `gittan doctor` to verify sources.")
            return

        rows: list[dict] = []
        shown_h = 0.0
        shown_sessions = 0

        for project_name, days_data in report.project_reports.items():
            proj_h = sum(d["hours"] for d in days_data.values())
            proj_s = sum(len(d["sessions"]) for d in days_data.values())
            if proj_h > 0:
                shown_h += proj_h
                shown_sessions += proj_s
                rows.append({"cells": [project_name, f"{proj_h:.1f}h", str(proj_s)]})

        total_h = sum(d.get("hours", 0.0) for d in report.overall_days.values())
        total_s = sum(len(d.get("sessions", [])) for d in report.overall_days.values())
        rows.append({"cells": ["Total", f"{total_h:.1f}h", str(total_s)], "total": True})

        w.caption(f"Hours Summary ({timeframe_str})")
        w.table(
            cols=[
                {"label": "Project",  "align": "left"},
                {"label": "Hours",    "align": "right", "type": "hours"},
                {"label": "Sessions", "align": "right", "type": "number"},
            ],
            rows=rows,
        )

        if shown_h > total_h + 0.01 or shown_sessions > total_s:
            w.note(
                f"project rows can overlap attribution. "
                f"Shown rows sum to {shown_h:.1f}h/{shown_sessions} sessions; "
                f"Total is unique timeline time: {total_h:.1f}h/{total_s} sessions."
            )

    except Exception as exc:
        logging.exception("Error fetching status for cast recording")
        w.note(f"Error fetching status: {type(exc).__name__}: {exc}")


# ── Doctor section ─────────────────────────────────────────────────────────────

def _record_doctor(w: CastWriter) -> None:
    w.prompt("gittan doctor")
    w.bee_box("Gittan Doctor", [
        "Checks source access, permissions, and config.",
        "Warnings are evidence gaps, not failures.",
        "Read-only: nothing is changed on your machine.",
    ])
    w.status_line("diagnose first, then approve fixes")
    w.caption("Gittan Health Check", center=True)
    w.health_table(_collect_doctor_rows())
    w.note(
        "warnings/errors for Mail/Chrome/Screen Time often mean Full Disk Access is "
        "required for your Terminal in System Settings > Privacy & Security."
    )
    w.next_steps([
        "Run `gittan report --today --source-summary` for a first local report.",
        "Use `gittan projects` if you want to refine project matching before reporting.",
    ])
    w.prompt()


def _collect_doctor_rows() -> list[dict[str, str]]:
    """Run all doctor checks and return structured rows — no Rich output."""
    from core.config import load_profiles, resolve_projects_config_path, resolve_worklog_path
    from core.git_project_bootstrap import assess_match_terms_coverage
    from collectors.lovable_desktop import lovable_desktop_history_candidates

    home = Path.home()
    rows: list[dict[str, str]] = []

    def ok(source: str, detail: str) -> None:
        rows.append({"source": source, "status": "ok", "detail": detail})

    def warn(source: str, detail: str) -> None:
        rows.append({"source": source, "status": "warn", "detail": detail})

    def _check_file(path: Path, label: str, ok_label: str = "Accessible") -> None:
        if not path.exists():
            warn(label, f"Not found: {path}")
        elif not os.access(path, os.R_OK):
            warn(label, "No read permission")
        else:
            ok(label, ok_label)

    def _check_db(path: Path, label: str, table_name: str) -> None:
        if not path.exists():
            warn(label, "DB not found")
            return
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            shutil.copy2(path, tmp.name)
            with sqlite3.connect(tmp.name) as conn:
                conn.execute(f"SELECT count(*) FROM {table_name} LIMIT 1").fetchone()
            ok(label, "DB query successful")
        except sqlite3.OperationalError as exc:
            if "database is locked" in str(exc):
                warn(label, "DB locked (try closing the app)")
            else:
                warn(label, f"Query failed: {exc}")
        except PermissionError:
            warn(label, "Full Disk Access required")
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    # CLI on PATH
    gittan_exe = shutil.which("gittan")
    if gittan_exe:
        ok("CLI (gittan on PATH)", gittan_exe)
    else:
        warn("CLI (gittan on PATH)", "Not on PATH; reinstall with: pipx install timelog-extract")

    # Project config + worklog
    projects_cfg = resolve_projects_config_path().expanduser()
    ns = argparse.Namespace(project="default-project", keywords="", email="")
    _profiles, loaded_cfg, workspace = load_profiles(str(projects_cfg), ns)
    worklog_path = resolve_worklog_path(None, loaded_cfg, workspace.get("worklog"), runtime_workspace_root())

    if projects_cfg.exists():
        ok("Project Config", "Accessible")
    else:
        warn("Project Config", f"Not found: {projects_cfg}")

    if worklog_path.exists():
        ok("Worklog (Local)", "Accessible")
    else:
        warn("Worklog (Local)", f"Not found: {worklog_path}")

    # Git match_terms coverage
    coverage = assess_match_terms_coverage(Path.cwd(), _profiles)
    if coverage.status == "ok":
        ok("Git match_terms coverage", coverage.detail)
    else:
        detail = coverage.detail
        if coverage.status == "warn" and getattr(coverage, "suggested_terms", None):
            detail += f" Suggested: {', '.join(coverage.suggested_terms)}"
        warn("Git match_terms coverage", detail)

    # Chrome History
    _check_db(
        home / "Library/Application Support/Google/Chrome/Default/History",
        "Chrome History", "urls",
    )

    # Lovable Desktop
    lh = lovable_desktop_history_candidates(home)
    if lh:
        _check_db(lh[0], "Lovable Desktop History", "urls")
    else:
        warn("Lovable Desktop History", "No History DB yet (browse in Lovable to create one)")

    # Apple Mail
    mail = home / "Library/Mail"
    if mail.exists():
        try:
            list(mail.glob("V[0-9]*"))
            ok("Apple Mail", "Folder accessible")
        except PermissionError:
            warn("Apple Mail", "Permission denied (Full Disk Access?)")
    else:
        warn("Apple Mail", "Path not found")

    # Cursor
    _check_file(
        home / "Library/Application Support/Cursor/User/globalStorage/storage.json",
        "Cursor Storage",
    )
    ckpt = home / "Library/Application Support/Cursor/User/globalStorage/anysphere.cursor-commits/checkpoints"
    if ckpt.exists():
        ok("Cursor Checkpoints", "Folder accessible")
    else:
        warn("Cursor Checkpoints", "Not found")

    # Screen Time
    st = home / "Library/Application Support/Knowledge/knowledgeC.db"
    if not st.exists():
        st = home / "Library/Application Support/KnowledgeC/knowledgeC.db"
    _check_db(st, "Screen Time DB", "ZOBJECT")

    # Claude Code
    if (home / ".claude/projects").exists():
        ok("Claude Code CLI", "Found projects")
    else:
        warn("Claude Code CLI", "Path not found")

    # GitHub Copilot
    copilot = home / ".copilot/logs"
    if copilot.exists():
        ok("GitHub Copilot CLI", f"Logs readable under {copilot}")
    else:
        warn("GitHub Copilot CLI", "Path not found")

    # GitHub Source
    gh_user = os.environ.get("GITHUB_USER", "").strip()
    gh_token = bool(os.environ.get("GITHUB_TOKEN", "").strip())
    if gh_user:
        ok("GitHub Source", f"Enabled (auto) for user '{gh_user}' — {'token present' if gh_token else 'no GITHUB_TOKEN'}")
    else:
        warn("GitHub Source", "Set GITHUB_USER env var to enable")

    # Toggl
    try:
        from collectors.toggl import toggl_source_enabled
        if toggl_source_enabled():
            ok("Toggl Source", "Configured")
        else:
            warn("Toggl Source", "Not configured (auto); set TOGGL_API_TOKEN to enable")
    except Exception:
        warn("Toggl Source", "Could not check Toggl configuration")

    return rows
