"""Typer commands: doctor, sources, projects."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import site
import sqlite3
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import questionary
import typer
from typing import Annotated, Optional

from core.cli_app import app
from core.cli_options import TimelogRunOptions, split_comma_separated_list
from core.cli_prompts import prompt_for_timeframe
from core.config import load_profiles, resolve_worklog_path
from outputs.terminal_theme import FAIL_ICON, NA_ICON, OK_ICON, STYLE_BORDER, STYLE_LABEL, STYLE_MUTED, WARN_ICON

# Same root as `core/report_service.REPO_ROOT` — default config/worklog live here, not CWD.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _dir_on_path(bin_dir: Path) -> bool:
    """True if bin_dir is a PATH entry (normalized)."""
    try:
        resolved = os.path.normcase(os.path.normpath(str(bin_dir.expanduser().resolve())))
    except OSError:
        resolved = os.path.normcase(os.path.normpath(str(bin_dir.expanduser())))
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if not p.strip():
            continue
        try:
            if os.path.normcase(os.path.normpath(p)) == resolved:
                return True
        except OSError:
            continue
    return False


def _add_cli_path_rows(table: Table, *, home: Path) -> None:
    """Warn when gittan exists but user script dirs are not on PATH (pip --user / pipx)."""
    gittan_exe = shutil.which("gittan")
    if gittan_exe:
        table.add_row("CLI (gittan on PATH)", OK_ICON, f"[{STYLE_MUTED}]{gittan_exe}[/{STYLE_MUTED}]")
        return
    if sys.platform == "win32":
        table.add_row(
            "CLI (gittan on PATH)",
            WARN_ICON,
            f"[{STYLE_MUTED}]Not on PATH. Add Python [bold]Scripts[/bold] to PATH or use [bold]py -m pip install --user[/bold]; see README.[/{STYLE_MUTED}]",
        )
        return
    hints: list[str] = []
    try:
        user_bin = Path(site.getuserbase()) / "bin"
        if (user_bin / "gittan").is_file() and not _dir_on_path(user_bin):
            hints.append(
                f"[{STYLE_MUTED}]pip --user: run [bold]export PATH=\"{user_bin}:$PATH\"[/bold] "
                f"(add that line to [bold]~/.zshrc[/bold] so new terminals work).[/{STYLE_MUTED}]"
            )
    except Exception:
        pass
    pipx_bin = home / ".local" / "bin"
    if (pipx_bin / "gittan").is_file() and not _dir_on_path(pipx_bin):
        hints.append(
            f"[{STYLE_MUTED}]pipx: run [bold]pipx ensurepath[/bold], then [bold]source ~/.zshrc[/bold] "
            f"or open a [bold]new[/bold] terminal ([bold]{pipx_bin}[/bold] must be on PATH).[/{STYLE_MUTED}]"
        )
    if hints:
        detail = " ".join(hints)
    else:
        detail = (
            f"[{STYLE_MUTED}]`gittan` not on PATH and no known script in user/bin or pipx. "
            f"Reinstall with [bold]pipx install timelog-extract[/bold] or see README.[/{STYLE_MUTED}]"
        )
    table.add_row("CLI (gittan on PATH)", WARN_ICON, detail)


@app.command()
def doctor(
    worklog: Annotated[
        Optional[str],
        typer.Option(
            "--worklog",
            help="Path to TIMELOG.md (overrides config; default matches report: config worklog, else project default).",
        ),
    ] = None,
):
    """Check health and permissions of all local data sources."""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    home = Path.home()
    projects_cfg = REPO_ROOT / "timelog_projects.json"
    _profiles, loaded_config_path, workspace = load_profiles(
        str(projects_cfg),
        argparse.Namespace(project="default-project", keywords="", email=""),
    )
    worklog_path = resolve_worklog_path(
        worklog,
        loaded_config_path,
        workspace.get("worklog"),
        REPO_ROOT,
    )

    table = Table(title="Gittan Health Check", box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = "bold #b7aed3"
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

    with console.status("[bold #b7aed3]Running diagnostics..."):
        _add_cli_path_rows(table, home=home)
        check_file(REPO_ROOT / "timelog_projects.json", "Project Config")
        check_file(worklog_path, "Worklog (Local)")

        chrome_path = home / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
        check_db(chrome_path, "Chrome History", "urls")

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
            home
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "globalStorage"
            / "anysphere.cursor-commits"
            / "checkpoints"
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

    console.print(table)
    console.print(
        "\n[#8f86ad]Note: warnings/errors for Mail/Chrome/Screen Time often mean Full Disk Access is required "
        "for your Terminal in System Settings > Privacy & Security.[/#8f86ad]\n"
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
        projects_config="timelog_projects.json",
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


@app.command()
def projects(
    config: Annotated[str, typer.Option(help="Path to projects config file")] = "timelog_projects.json",
):
    """Manage project profiles interactively."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    config_path = Path(config)

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                data = {"projects": data}
        except Exception as e:
            console.print(f"[red]Error reading config: {e}[/red]")
            raise typer.Exit(code=1) from e
    else:
        data = {"projects": [], "worklog": "TIMELOG.md"}

    def save():
        config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[green]Saved to {config_path}[/green]")

    while True:
        action = questionary.select(
            "Project Management",
            choices=[
                "List Projects",
                "Add New Project",
                "Edit Project",
                "Remove Project",
                "Set Worklog Path",
                "Save & Exit",
                "Cancel",
            ],
        ).ask()

        if action == "Cancel" or not action:
            break

        if action == "Save & Exit":
            save()
            break

        if action == "List Projects":
            table = Table(title="Project Profiles")
            table.add_column("Name (ID)", style="cyan")
            table.add_column("Customer", style="magenta")
            table.add_column("Match Terms", style="dim")

            for p in data.get("projects", []):
                table.add_row(
                    p.get("name", "N/A"),
                    p.get("customer", p.get("name", "N/A")),
                    ", ".join(p.get("match_terms", [])),
                )
            console.print(table)

        if action == "Set Worklog Path":
            current_wl = data.get("worklog", "TIMELOG.md")
            new_wl = questionary.text("Worklog path:", default=current_wl).ask()
            if new_wl:
                data["worklog"] = new_wl

        if action == "Add New Project" or action == "Edit Project":
            project = {}
            is_edit = action == "Edit Project"

            if is_edit:
                names = [p["name"] for p in data.get("projects", [])]
                if not names:
                    console.print("[yellow]No projects to edit.[/yellow]")
                    continue
                target_name = questionary.select("Select project to edit:", choices=names).ask()
                project = next(p for p in data["projects"] if p["name"] == target_name)

            name = project.get("name", "")
            if not is_edit:
                name = questionary.text("Project Name (unique ID):").ask()
                if not name:
                    continue

            customer = questionary.text("Customer (display name):", default=project.get("customer", name)).ask()
            if customer is None:
                continue

            match_terms = questionary.text(
                "Match Terms (comma separated):",
                default=", ".join(project.get("match_terms", [])),
            ).ask()
            if match_terms is None:
                continue

            tracked_urls = questionary.text(
                "Tracked AI URLs (comma separated):",
                default=", ".join(project.get("tracked_urls", [])),
            ).ask()
            if tracked_urls is None:
                continue

            email = questionary.text("Email filter (sender/receiver):", default=project.get("email", "")).ask()
            if email is None:
                continue

            title = questionary.text("Invoice Title:", default=project.get("invoice_title", "")).ask()
            if title is None:
                continue

            desc = questionary.text("Invoice Description:", default=project.get("invoice_description", "")).ask()
            if desc is None:
                continue

            new_project = {
                "name": name,
                "customer": customer,
                "match_terms": split_comma_separated_list(match_terms),
                "tracked_urls": split_comma_separated_list(tracked_urls),
                "email": email,
                "invoice_title": title,
                "invoice_description": desc,
                "enabled": True,
            }

            if is_edit:
                idx = next(i for i, p in enumerate(data["projects"]) if p["name"] == target_name)
                data["projects"][idx] = new_project
            else:
                if "projects" not in data:
                    data["projects"] = []
                data["projects"].append(new_project)

            console.print("[green]Project updated in memory. Remember to 'Save & Exit'.[/green]")

        if action == "Remove Project":
            names = [p["name"] for p in data.get("projects", [])]
            if not names:
                console.print("[yellow]No projects to remove.[/yellow]")
                continue
            target_name = questionary.select("Select project to remove:", choices=names).ask()
            if questionary.confirm(f"Are you sure you want to remove '{target_name}'?").ask():
                data["projects"] = [p for p in data["projects"] if p["name"] != target_name]
                console.print("[red]Project removed from memory.[/red]")
