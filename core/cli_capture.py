"""Typer command: capture — record this device's AI session evidence."""

from __future__ import annotations

from typing import Annotated, List, Optional

import typer

from core.cli_app import app


@app.command("capture")
def capture(
    date_from: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD). Defaults to today.")] = None,
    date_to: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD). Defaults to today.")] = None,
    device: Annotated[Optional[str], typer.Option("--device", help="Name this device in the evidence (default: host name).")] = None,
    home: Annotated[Optional[str], typer.Option("--home", help="Read session transcripts from this HOME instead of yours.")] = None,
    export: Annotated[Optional[str], typer.Option("--export", help="Write records to PATH instead of this device's ledger — for a device whose store is not the canonical one.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Report what would be captured; write nothing.")] = False,
    if_enabled: Annotated[bool, typer.Option("--if-enabled", help="Do nothing unless \"shadow_log\" is on in config — for timers and hooks.")] = False,
    source: Annotated[Optional[List[str]], typer.Option("--source", help="Capture only this source (repeatable). Default: all. Try an unknown name to list them.")] = None,
    projects_config: Annotated[Optional[str], typer.Option("--projects-config", help="Path to timelog_projects.json.")] = None,
) -> None:
    """Capture this device's AI session evidence into the shadow log.

    A phone, a laptop and a cloud container are all devices you work on, but
    only the device that ran the session holds its transcript. Capture writes
    that evidence to the ledger, tagged with the device, so a day's work
    survives the machine it happened on.

    Merging is idempotent: the same session captured twice — or captured here
    and imported from an export — lands as one record, never two.
    """
    from datetime import datetime, timezone
    from pathlib import Path
    from types import SimpleNamespace

    from rich.console import Console

    from core.analytics import get_date_range
    from core.config import load_profiles, resolve_projects_config_path
    from core.session_capture import capture_device_evidence
    from outputs.terminal_theme import (
        CLR_VALUE_ORANGE,
        FAIL_ICON,
        STYLE_LABEL,
        STYLE_MUTED,
    )

    local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    console = Console()

    read_home = Path(home).expanduser() if home else Path.home()
    if not read_home.is_dir():
        console.print(f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: no such HOME: {read_home}[/{CLR_VALUE_ORANGE}]")
        console.print(f"[{STYLE_MUTED}]Next: Pass --home with the path that holds the session transcripts.[/{STYLE_MUTED}]")
        raise typer.Exit(code=1)

    config_path = str(projects_config) if projects_config else str(resolve_projects_config_path())
    profiles, _cfg, _workspace = load_profiles(
        config_path, SimpleNamespace(project="", keywords="", email="")
    )
    dt_from, dt_to = get_date_range(date_from, date_to, local_tz)

    try:
        summary = capture_device_evidence(
            profiles,
            dt_from,
            dt_to,
            home=read_home,
            # `--home` redirects *reading* only. The ledger is always the
            # operator data dir (`$GITTAN_HOME/evidence` or `~/.gittan/evidence`),
            # which report / evidence / doctor already read — never a private
            # alternate store. `--export` writes a portable file instead.
            device=device,
            export_to=export,
            dry_run=dry_run,
            if_enabled=if_enabled,
            config_path=config_path,
            sources=list(source) if source else None,
        )
    except ValueError as exc:
        # Raised for an unknown --source; the message already names the valid ones.
        console.print(f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: {exc}[/{CLR_VALUE_ORANGE}]")
        console.print(f"[{STYLE_MUTED}]Next: Pass --source with one of the names listed above.[/{STYLE_MUTED}]")
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        console.print(f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: {exc}[/{CLR_VALUE_ORANGE}]")
        console.print(f"[{STYLE_MUTED}]Next: Check --home and --export point at readable paths.[/{STYLE_MUTED}]")
        raise typer.Exit(code=1) from exc

    if summary.get("skipped_reason"):
        console.print(
            f"[{STYLE_MUTED}]Capture skipped: {summary['skipped_reason']}. "
            f'Enable with "shadow_log": "on" in timelog_projects.json.[/{STYLE_MUTED}]'
        )
        return

    console.print(
        f"[bold {STYLE_LABEL}]Session capture[/bold {STYLE_LABEL}] — device "
        f"[{CLR_VALUE_ORANGE}]{summary['device']}[/{CLR_VALUE_ORANGE}]"
    )
    console.print(f"Events found: [{CLR_VALUE_ORANGE}]{summary['collected']}[/{CLR_VALUE_ORANGE}]")

    if summary["dry_run"]:
        console.print(f"[{STYLE_MUTED}]Dry run — nothing written.[/{STYLE_MUTED}]")
    elif summary["collected"] == 0:
        console.print(f"[{STYLE_MUTED}]Nothing to capture in this window.[/{STYLE_MUTED}]")
    else:
        console.print(
            f"Appended: [{CLR_VALUE_ORANGE}]{summary['appended']}[/{CLR_VALUE_ORANGE}] "
            f"(already present: {summary['skipped']})"
        )
        console.print(f"[{STYLE_MUTED}]Written to: {summary['destination']}[/{STYLE_MUTED}]")

    if summary.get("sources"):
        console.print(f"[{STYLE_MUTED}]Sources: {', '.join(summary['sources'])}[/{STYLE_MUTED}]")

    if summary["projects"]:
        console.print(f"[{STYLE_MUTED}]Projects: {', '.join(summary['projects'])}[/{STYLE_MUTED}]")

    if export and not summary["dry_run"] and summary["collected"]:
        console.print(
            f"[{STYLE_MUTED}]Next: On your main device, run "
            f"`gittan evidence --import {summary['destination']}`.[/{STYLE_MUTED}]"
        )
