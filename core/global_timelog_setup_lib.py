"""Shared setup implementation for onboarding wizard (doctor, smoke, project config)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import sysconfig
from datetime import datetime
from pathlib import Path

import questionary
import typer
from rich.console import Console
from rich import box
from rich.table import Table

from core.global_timelog_machine_setup import run_global_timelog_setup
from core.onboarding_guidance import build_setup_next_steps, print_next_steps
from core.setup_github_env import configure_github_env_for_setup
from core.setup_projects_config_bootstrap import ensure_projects_config
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED

REPO_ROOT = Path(__file__).resolve().parent.parent


def _timestamped_backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")


def _looks_like_projects_config(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    projects = payload.get("projects")
    return isinstance(projects, list)


def _ensure_minimal_projects_config(
    console,
    *,
    yes: bool,
    dry_run: bool,
    bootstrap_root: str | None = None,
) -> tuple[str, str, list[str]]:
    """
    Ensure a minimal timelog projects configuration is present in the current working directory.

    This may create or validate a `timelog_projects.json` file and produce actionable notes and follow-up steps. Behavior is affected by `yes` (non-interactive confirmation), `dry_run` (preview without writing), and an optional `bootstrap_root` to seed configuration.

    Parameters:
        console: Console-like object used for prompts and informational output.
        yes (bool): If True, proceed without interactive confirmation.
        dry_run (bool): If True, show what would change but do not write files.
        bootstrap_root (str | None): Optional path used to bootstrap project discovery; when None no special bootstrap root is used.

    Returns:
        status (str): High-level result status such as `"PASS"`, `"ACTION_REQUIRED"`, or similar.
        notes (str): Human-readable notes or summary about actions taken or required.
        next_steps (list[str]): Ordered list of follow-up steps the user should perform.
    """
    result = ensure_projects_config(
        console=console,
        yes=yes,
        dry_run=dry_run,
        bootstrap_root=bootstrap_root,
        config_path=Path.cwd() / "timelog_projects.json",
        timestamped_backup_path_fn=_timestamped_backup_path,
        looks_like_projects_config_fn=_looks_like_projects_config,
    )
    return result.status, result.notes, result.next_steps


def _print_environment_status(console) -> None:
    table = Table(title="Environment checks", box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = "bold #f0abfc"
    table.add_column("Check", style=STYLE_LABEL)
    table.add_column("Status")
    table.add_column("Details", style="dim")
    gittan_in_path = shutil.which("gittan")
    scripts_path = sysconfig.get_path("scripts")
    path_values = {str(Path(part).expanduser()) for part in os.environ.get("PATH", "").split(":") if part}
    scripts_in_path = str(Path(scripts_path).expanduser()) in path_values
    table.add_row("`gittan` command", "[green]OK[/green]" if gittan_in_path else "[yellow]MISSING[/yellow]", gittan_in_path or "Command not currently available in PATH")
    table.add_row("Python scripts PATH", "[green]OK[/green]" if scripts_in_path else "[yellow]ACTION[/yellow]", scripts_path if scripts_in_path else f"Add to PATH: {scripts_path}")
    github_user = os.environ.get("GITHUB_USER", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    table.add_row("GitHub user env", "[green]SET[/green]" if github_user else "[dim]optional[/dim]", github_user or "(not set)")
    table.add_row("GitHub token env", "[green]SET[/green]" if github_token else "[dim]optional[/dim]", "(set)" if github_token else "(not set)")
    console.print(table)
    if not scripts_in_path:
        shell = os.environ.get("SHELL", "")
        shell_name = Path(shell).name if shell else ""
        rc_file = "~/.zshrc" if shell_name == "zsh" else "~/.bashrc" if shell_name == "bash" else "~/.profile"
        console.print(f"[cyan]Detected shell:[/cyan] {shell or '(unknown)'}")
        console.print(f"[cyan]Suggested profile file:[/cyan] {rc_file}")
        console.print(f"[yellow]Tip:[/yellow] add this to your shell profile: `export PATH=\"{scripts_path}:$PATH\"`")
        console.print(f"[dim]Apply now in current terminal:[/dim] `export PATH=\"{scripts_path}:$PATH\"`")


def _print_setup_header(console, *, dry_run: bool) -> None:
    print_command_hero(console, "setup")
    if dry_run:
        console.print("[yellow]Dry run mode:[/yellow] commands are previewed; no system files are changed.")
    console.print("")


def _print_setup_environment_loaded(console) -> None:
    projects_present = int((Path.cwd() / "timelog_projects.json").exists())
    github_user_set = int(bool((os.environ.get("GITHUB_USER") or "").strip()))
    github_token_set = int(bool((os.environ.get("GITHUB_TOKEN") or "").strip()))
    console.print(
        "[dim]Environment loaded:[/dim] "
        f"{projects_present} project config, {github_user_set} GitHub user env, {github_token_set} GitHub token env"
    )
    console.print("")


def _run_doctor_check(console, *, dry_run: bool) -> str:
    if dry_run:
        console.print("\n[bold]Doctor output[/bold]")
        console.print("[yellow]Dry run:[/yellow] would run `gittan doctor`.")
        return "PASS (dry-run)"
    entry = REPO_ROOT / "timelog_extract.py"
    console.print("\n[bold]Doctor output[/bold]")
    console.print("[dim]Running `gittan doctor` inside setup...[/dim]")
    completed = subprocess.run([sys.executable, str(entry), "doctor"], check=False, capture_output=True, text=True, cwd=str(Path.cwd()))
    console.print("[green]Doctor check completed.[/green]" if completed.returncode == 0 else "[yellow]Doctor check reported issues.[/yellow]")
    if completed.stdout:
        console.print(completed.stdout.strip())
    if completed.stderr:
        console.print(f"[dim]{completed.stderr.strip()}[/dim]")
    return "PASS" if completed.returncode == 0 else "ACTION_REQUIRED"


def _run_smoke_report(console, *, dry_run: bool) -> str:
    if dry_run:
        console.print("[yellow]Dry run:[/yellow] would run `gittan report --last-week --include-uncategorized --format json --quiet`.")
        return "PASS (dry-run)"
    entry = REPO_ROOT / "timelog_extract.py"
    with console.status("[bold blue]Running smoke report...[/bold blue]"):
        completed = subprocess.run(
            [sys.executable, str(entry), "report", "--last-week", "--include-uncategorized", "--format", "json", "--quiet"],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
        )
    if completed.returncode != 0:
        console.print("[yellow]Smoke report failed; check output below.[/yellow]")
        if completed.stderr:
            console.print(f"[dim]{completed.stderr.strip()}[/dim]")
        if completed.stdout:
            console.print(completed.stdout.strip()[:1200])
        return "FAIL"
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and payload.get("schema") == "timelog_extract.truth_payload":
        totals = payload.get("totals", {})
        console.print("[green]Smoke report passed.[/green]")
        console.print(f"[dim]schema={payload.get('schema')} | events={totals.get('event_count','n/a')} | days={totals.get('days_with_activity','n/a')} | hours={totals.get('hours_estimated','n/a')}[/dim]")
        return "PASS"
    else:
        console.print("[yellow]Smoke report completed, but output was not recognized as truth payload JSON.[/yellow]")
        if completed.stdout:
            console.print(completed.stdout.strip()[:1200])
        if completed.stderr:
            console.print(f"[dim]{completed.stderr.strip()}[/dim]")
        return "ACTION_REQUIRED"


def run_setup_wizard(console, *, yes: bool, dry_run: bool, skip_smoke: bool, bootstrap_root: str | None = None) -> None:
    _print_setup_header(console, dry_run=dry_run)
    summary_rows: list[tuple[str, str, str]] = []
    next_steps: list[str] = []
    _print_environment_status(console)
    _print_setup_environment_loaded(console)
    summary_rows.append(("Environment checks", "PASS", "Printed PATH and optional env status."))
    try:
        github_env_status, github_env_note, github_env_steps = configure_github_env_for_setup(
            console, yes=yes, dry_run=dry_run
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        console.print(f"[yellow]GitHub env bootstrap could not complete:[/yellow] {exc}")
        github_env_status = "ACTION_REQUIRED"
        github_env_note = f"GitHub env bootstrap failed: {exc}"
        github_env_steps = [
            "Set GITHUB_USER and optionally GITHUB_TOKEN manually, then rerun `gittan doctor --github-source auto`."
        ]
    summary_rows.append(("GitHub env bootstrap", github_env_status, github_env_note))
    next_steps.extend(github_env_steps)
    should_setup_timelog = yes or questionary.confirm("Configure global timelog automation now?", default=True).ask()
    if should_setup_timelog:
        run_global_timelog_setup(console, yes=yes, dry_run=dry_run)
        summary_rows.append(("Global timelog automation", "PASS" if not dry_run else "PASS (dry-run)", "Configured or previewed global hooks + global ignore."))
    else:
        console.print("[yellow]Skipped global timelog automation.[/yellow]")
        summary_rows.append(("Global timelog automation", "SKIPPED", "User skipped this step."))
    projects_status, projects_note, project_steps = _ensure_minimal_projects_config(
        console,
        yes=yes,
        dry_run=dry_run,
        bootstrap_root=bootstrap_root,
    )
    summary_rows.append(("Project config bootstrap", projects_status, projects_note))
    next_steps.extend(project_steps)
    doctor_status = _run_doctor_check(console, dry_run=dry_run)
    summary_rows.append(("Doctor check", doctor_status, "Ran (or previewed) source/permission diagnostics."))
    smoke_status = "SKIPPED"
    if skip_smoke:
        console.print("[yellow]Skipped smoke report (--skip-smoke).[/yellow]")
        summary_rows.append(("Smoke report", "SKIPPED", "Skipped via --skip-smoke flag."))
    else:
        should_smoke = yes or questionary.confirm("Run final smoke report now?", default=True).ask()
        if should_smoke:
            smoke_status = _run_smoke_report(console, dry_run=dry_run)
            summary_rows.append(("Smoke report", smoke_status, "Ran (or previewed) JSON smoke report command."))
        else:
            console.print("[yellow]Skipped smoke report.[/yellow]")
            summary_rows.append(("Smoke report", "SKIPPED", "User skipped this step."))
            smoke_status = "SKIPPED"
    summary_table = Table(title="Setup summary", box=box.ROUNDED)
    summary_table.border_style = STYLE_BORDER
    summary_table.header_style = "bold #f0abfc"
    summary_table.add_column("Step", style=STYLE_LABEL)
    summary_table.add_column("Result")
    summary_table.add_column("Notes", style=STYLE_MUTED)
    for step, result, notes in summary_rows:
        if result.startswith("PASS"):
            style = "green"
        elif result == "FAIL":
            style = "red"
        elif result in ("ACTION_REQUIRED", "SKIPPED"):
            style = "yellow"
        else:
            style = "yellow"
        summary_table.add_row(step, f"[{style}]{result}[/{style}]", notes)
    console.print("\n")
    console.print(summary_table)
    console.print("\n")
    next_steps.extend(
        build_setup_next_steps(
            dry_run=dry_run,
            projects_status=projects_status,
            doctor_status=doctor_status,
            smoke_status=smoke_status,
        )
    )
    print_next_steps(console, list(dict.fromkeys(next_steps)))
    console.print("\n[green]Setup wizard completed.[/green]")
