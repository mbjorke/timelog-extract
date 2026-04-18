"""Shared setup implementation for global timelog and onboarding wizard."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import sysconfig
from datetime import datetime
from pathlib import Path

import questionary
import typer
from rich.console import Console
from core.git_project_bootstrap import discover_local_git_repos
from core.global_timelog_hook_script import HOOK_BODY
from core.onboarding_guidance import build_setup_next_steps, print_next_steps
from core.setup_github_env import configure_github_env_for_setup
from core.setup_projects_config_bootstrap import ensure_projects_config
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED

REPO_ROOT = Path(__file__).resolve().parent.parent
GITTAN_CONFIG_DIR = Path.home() / ".gittan"
GITTAN_SCOPE_FILE = GITTAN_CONFIG_DIR / "timelog_repos.txt"
GITTAN_FILENAME_FILE = GITTAN_CONFIG_DIR / "timelog_filename"


def _run_git_config(args: list[str], *, dry_run: bool) -> None:
    if dry_run:
        return
    subprocess.run(["git", "config", "--global", *args], check=True, capture_output=True, text=True)


def _read_global_git_config(key: str) -> str:
    completed = subprocess.run(
        ["git", "config", "--global", "--get", key],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _ensure_executable(path: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR)


def _ensure_timelog_ignored(ignore_path: Path, *, dry_run: bool, timelog_entry: str = "TIMELOG.md") -> bool:
    existing = ignore_path.read_text(encoding="utf-8") if ignore_path.exists() else ""
    existing_lines = [line.strip() for line in existing.splitlines()]
    # Check if both the configured entry and "TIMELOG.md" are present
    has_configured = timelog_entry in existing_lines
    has_default = "TIMELOG.md" in existing_lines
    if has_configured and has_default:
        return False
    if dry_run:
        return True
    with ignore_path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        # Append missing entries
        if not has_configured:
            handle.write(f"{timelog_entry}\n")
        if not has_default:
            handle.write("TIMELOG.md\n")
    return True


def _is_managed_hook(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return "managed-by-gittan: global-timelog" in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _timestamped_backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")


def _looks_like_projects_config(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    projects = payload.get("projects")
    return isinstance(projects, list)


def _discover_git_repos(console: Console) -> list[Path]:
    candidates: list[Path] = []
    roots = [Path.cwd(), Path.home() / "Workspace", Path.home() / "Code", Path.home() / "Projects", Path.home() / "Developer"]
    seen_roots: set[Path] = set()
    console.print("[cyan]Scanning local directories for git repositories...[/cyan]")
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        if root in seen_roots or not root.exists() or not root.is_dir():
            continue
        seen_roots.add(root)
        discovered = discover_local_git_repos(root, max_depth=3, limit=120)
        console.print(f"[dim]- scanned {root} -> {len(discovered)} candidate repos[/dim]")
        candidates.extend(discovered)
        if len(candidates) >= 240:
            break
    unique = sorted({p.resolve() for p in candidates}, key=lambda p: str(p).lower())
    if not unique:
        console.print("[yellow]Repository scan found no candidates in common workspace roots.[/yellow]")
        return []
    # Filter out nested repositories: remove ancestor paths if their nested children are present
    filtered: list[Path] = []
    for p in unique:
        # Drop p if there exists another path q where q is relative to p (i.e., p is an ancestor of q)
        is_ancestor = any(q != p and p in q.parents for q in unique)
        if not is_ancestor:
            filtered.append(p)
    console.print(f"[green]Repository scan complete:[/green] {len(filtered[:120])} candidate repos available for selection.")
    return filtered[:120]


def _configure_timelog_scope_and_name(console, *, yes: bool, dry_run: bool) -> None:
    timelog_name = "TIMELOG.md"
    scope_mode = "all"
    selected: list[str] = []
    if not yes:
        # Validate timelog path: reject absolute paths and parent components
        while True:
            candidate = (
                questionary.text("Timelog file path inside each repo (relative path):", default="TIMELOG.md").ask()
                or "TIMELOG.md"
            ).strip()
            if os.path.isabs(candidate):
                console.print("[yellow]Error: Absolute paths are not allowed. Please enter a relative path.[/yellow]")
                continue
            if ".." in Path(candidate).parts:
                console.print("[yellow]Error: Parent directory components (..) are not allowed.[/yellow]")
                continue
            timelog_name = candidate
            break
        scope_mode = questionary.select(
            "Where should global timelog automation run?",
            choices=[
                "All repositories (fastest, recommended)",
                "Choose specific repositories (slower, advanced)",
            ],
        ).ask() or "All repositories (fastest, recommended)"
        if scope_mode.startswith("Choose specific"):
            repos = _discover_git_repos(console)
            if repos:
                selected = questionary.checkbox("Select repositories to include:", choices=[str(repo) for repo in repos]).ask() or []
            else:
                console.print(
                    "[yellow]No repositories found during scan.[/yellow] "
                    "Continuing safely with [bold]all repositories[/bold] scope."
                )
                scope_mode = "all"

    if dry_run:
        console.print(f"[yellow]Dry run:[/yellow] would set timelog file path to `{timelog_name}`.")
        if selected:
            console.print(f"[yellow]Dry run:[/yellow] would write {len(selected)} selected repos to {GITTAN_SCOPE_FILE}.")
        elif scope_mode.startswith("Choose specific"):
            console.print(f"[yellow]Dry run:[/yellow] would write empty allowlist to {GITTAN_SCOPE_FILE} (no repos selected).")
        else:
            console.print("[yellow]Dry run:[/yellow] would configure scope for all git repositories.")
        return

    GITTAN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    GITTAN_FILENAME_FILE.write_text(timelog_name + "\n", encoding="utf-8")
    if selected:
        GITTAN_SCOPE_FILE.write_text("\n".join(selected) + "\n", encoding="utf-8")
    elif scope_mode.startswith("Choose specific"):
        # Empty selection explicitly means no repos - write empty file
        GITTAN_SCOPE_FILE.write_text("", encoding="utf-8")
    elif GITTAN_SCOPE_FILE.exists():
        GITTAN_SCOPE_FILE.unlink()


def run_global_timelog_setup(console, *, yes: bool, dry_run: bool) -> None:
    from rich.table import Table
    from rich import box

    home = Path.home()
    hooks_dir = home / ".githooks"
    hook_path = hooks_dir / "post-commit"
    ignore_path = home / ".gitignore_global"
    current_hooks_path = _read_global_git_config("core.hooksPath")
    current_excludes_file = _read_global_git_config("core.excludesFile")

    print_command_hero(console, "setup-global-timelog")
    console.print("This will configure global git hooks so each commit appends an entry to repo-local `TIMELOG.md`.")
    table = Table(title="Current global git status", box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = "bold #b7aed3"
    table.add_column("Setting", style=STYLE_LABEL)
    table.add_column("Current value", style=STYLE_MUTED)
    table.add_row("core.hooksPath", current_hooks_path or "(not set)")
    table.add_row("core.excludesFile", current_excludes_file or "(not set)")
    table.add_row("Hook file", str(hook_path) if hook_path.exists() else "(missing)")
    table.add_row("Global ignore", str(ignore_path) if ignore_path.exists() else "(missing)")
    table.add_row("Timelog filename config", str(GITTAN_FILENAME_FILE) if GITTAN_FILENAME_FILE.exists() else "(missing)")
    table.add_row("Repo scope file", str(GITTAN_SCOPE_FILE) if GITTAN_SCOPE_FILE.exists() else "(missing)")
    console.print(table)
    if dry_run:
        console.print("[yellow]Dry run mode:[/yellow] no changes will be made.")
    if not (yes or questionary.confirm("Proceed with setup?", default=True).ask()):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(code=0)

    try:
        if not dry_run:
            hooks_dir.mkdir(parents=True, exist_ok=True)
        _run_git_config(["core.hooksPath", str(hooks_dir)], dry_run=dry_run)
        if hook_path.exists():
            if _is_managed_hook(hook_path):
                console.print("[green]Managed hook already present; keeping existing file.[/green]")
            else:
                console.print("[yellow]Existing hook is not managed by Gittan, so overwrite confirmation is required.[/yellow]")
                overwrite = yes or questionary.confirm(
                    f"Hook already exists at {hook_path}. Overwrite with managed script?",
                    default=True,
                ).ask()
                if not overwrite:
                    console.print("[yellow]Skipped hook overwrite; keeping existing hook file.[/yellow]")
                elif not dry_run:
                    hook_path.write_text(HOOK_BODY, encoding="utf-8")
        elif not dry_run:
            hook_path.write_text(HOOK_BODY, encoding="utf-8")
        if not dry_run and hook_path.exists():
            _ensure_executable(hook_path, dry_run=dry_run)
        if not dry_run:
            ignore_path.touch(exist_ok=True)
        _run_git_config(["core.excludesFile", str(ignore_path)], dry_run=dry_run)
        _configure_timelog_scope_and_name(console, yes=yes, dry_run=dry_run)
        # Get configured timelog name for gitignore (after configuration is set)
        configured_timelog = GITTAN_FILENAME_FILE.read_text(encoding="utf-8").splitlines()[0].strip() if GITTAN_FILENAME_FILE.exists() else "TIMELOG.md"
        added_ignore = _ensure_timelog_ignored(ignore_path, dry_run=dry_run, timelog_entry=configured_timelog)
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]Git config command failed:[/red] {exc}")
        if exc.stderr:
            console.print(exc.stderr.strip())
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        console.print(f"[red]File operation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print("\n[green]Setup completed.[/green]" if not dry_run else "\n[green]Dry run completed.[/green]")
    console.print("Added `TIMELOG.md` to global gitignore." if added_ignore else "`TIMELOG.md` already present in global gitignore.")
    verify_hooks = _read_global_git_config("core.hooksPath") if not dry_run else str(hooks_dir)
    verify_excludes = _read_global_git_config("core.excludesFile") if not dry_run else str(ignore_path)
    console.print("\n[bold]Verify:[/bold]")
    console.print(f"- core.hooksPath = {verify_hooks or '(not set)'}")
    console.print(f"- core.excludesFile = {verify_excludes or '(not set)'}")
    if not dry_run and hook_path.exists():
        is_exec = bool(hook_path.stat().st_mode & stat.S_IXUSR)
        console.print(f"- post-commit executable = {'yes' if is_exec else 'no'}")
        timelog_name = GITTAN_FILENAME_FILE.read_text(encoding="utf-8").splitlines()[0].strip() if GITTAN_FILENAME_FILE.exists() else "TIMELOG.md"
        console.print(f"- timelog file inside repo = {timelog_name}")
        if GITTAN_SCOPE_FILE.exists():
            repo_count = len([line for line in GITTAN_SCOPE_FILE.read_text(encoding="utf-8").splitlines() if line.strip()])
            console.print(f"- repo scope = selected list ({repo_count} repos)")
        else:
            console.print("- repo scope = all git repositories")
        console.print("\nReference: `docs/runbooks/global-timelog-setup.md`")


def _ensure_minimal_projects_config(
    console,
    *,
    yes: bool,
    dry_run: bool,
    bootstrap_root: str | None = None,
) -> tuple[str, str, list[str]]:
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
    from rich.table import Table
    from rich import box

    table = Table(title="Environment checks", box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = "bold #b7aed3"
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
    from rich.table import Table
    from rich import box

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
    summary_table.header_style = "bold #b7aed3"
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