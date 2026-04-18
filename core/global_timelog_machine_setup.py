"""Global git hooks + timelog path/scope configuration for `setup-global-timelog`."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import questionary
import typer
from rich.console import Console
from rich import box
from rich.table import Table

from core.git_project_bootstrap import discover_local_git_repos
from core.global_timelog_hook_script import HOOK_BODY
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED

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
    has_configured = timelog_entry in existing_lines
    has_default = "TIMELOG.md" in existing_lines
    if has_configured and has_default:
        return False
    if dry_run:
        return True
    with ignore_path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
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
    filtered: list[Path] = []
    for p in unique:
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
        GITTAN_SCOPE_FILE.write_text("", encoding="utf-8")
    elif GITTAN_SCOPE_FILE.exists():
        GITTAN_SCOPE_FILE.unlink()


def run_global_timelog_setup(console, *, yes: bool, dry_run: bool) -> None:
    """
    Configure global git hooks and global gitignore to enable repository-level timelogging.

    Depending on user confirmation, this will set `core.hooksPath` and `core.excludesFile`, install or update a managed `post-commit` hook, write timelog filename and scope configuration, and ensure the configured timelog filename (and the default "TIMELOG.md") are present in the global gitignore. When `dry_run` is true no changes are written; when `yes` is true prompts are skipped and defaults/confirmations are accepted.

    Parameters:
        console: Rich console-like object used for printing status and prompting the user.
        yes (bool): When true, skip interactive confirmations and accept default actions.
        dry_run (bool): When true, show the actions that would be taken without modifying files or git config.

    Raises:
        typer.Exit: Raised with code 0 if the user cancels; raised with a non-zero code on git or filesystem errors.
    """
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
    table.header_style = "bold #f0abfc"
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
