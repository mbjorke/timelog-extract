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
from textwrap import dedent

import questionary
import typer

REPO_ROOT = Path(__file__).resolve().parent.parent
GITTAN_CONFIG_DIR = Path.home() / ".gittan"
GITTAN_SCOPE_FILE = GITTAN_CONFIG_DIR / "timelog_repos.txt"
GITTAN_FILENAME_FILE = GITTAN_CONFIG_DIR / "timelog_filename"

HOOK_BODY = dedent(
    """\
    #!/bin/zsh
    # managed-by-gittan: global-timelog
    set -euo pipefail

    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
    ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    [[ -n "${ROOT_DIR:-}" ]] || exit 0

    GITTAN_CFG_DIR="$HOME/.gittan"
    SCOPE_FILE="$GITTAN_CFG_DIR/timelog_repos.txt"
    FILENAME_FILE="$GITTAN_CFG_DIR/timelog_filename"
    TIMELOG_NAME="TIMELOG.md"
    if [[ -f "$FILENAME_FILE" ]]; then
      CANDIDATE="$(head -n 1 "$FILENAME_FILE" 2>/dev/null | tr -d '\r')"
      if [[ -n "${CANDIDATE:-}" ]]; then
        TIMELOG_NAME="$CANDIDATE"
      fi
    fi
    if [[ -f "$SCOPE_FILE" ]]; then
      if ! rg -Fx -- "$ROOT_DIR" "$SCOPE_FILE" >/dev/null 2>&1; then
        exit 0
      fi
    fi

    TIMELOG_FILE="$ROOT_DIR/$TIMELOG_NAME"
    mkdir -p "$(dirname "$TIMELOG_FILE")"
    TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"
    SUBJECT="$(git log -1 --pretty=%s)"

    if [[ ! -f "$TIMELOG_FILE" ]]; then
      {
        echo "# TIMELOG"
        echo
      } > "$TIMELOG_FILE"
    fi

    {
      echo "## $TIMESTAMP"
      echo "- Commit: $SUBJECT"
      echo
    } >> "$TIMELOG_FILE"
    """
)


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


def _discover_git_repos() -> list[Path]:
    candidates: list[Path] = []
    roots = [Path.cwd(), Path.home() / "Workspace", Path.home() / "Code", Path.home() / "Projects", Path.home() / "Developer"]
    seen_roots: set[Path] = set()
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        if root in seen_roots or not root.exists() or not root.is_dir():
            continue
        seen_roots.add(root)
        if (root / ".git").exists():
            candidates.append(root)
        for git_dir in root.glob("**/.git"):
            repo = git_dir.parent
            if not repo.is_dir():
                continue
            repo_s = str(repo)
            if "/.cache/" in repo_s or "/Library/" in repo_s:
                continue
            candidates.append(repo)
            if len(candidates) >= 300:
                break
        if len(candidates) >= 300:
            break
    unique = sorted({p.resolve() for p in candidates}, key=lambda p: str(p).lower())
    return unique[:200]


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
            choices=["All git repositories (recommended default)", "Only selected repositories (scan and choose)"],
        ).ask() or "All git repositories (recommended default)"
        if scope_mode.startswith("Only selected"):
            repos = _discover_git_repos()
            if repos:
                selected = questionary.checkbox("Select repositories to include:", choices=[str(repo) for repo in repos]).ask() or []
            else:
                console.print("[yellow]No repositories found during scan; keeping scope = all repos.[/yellow]")
                scope_mode = "all"

    if dry_run:
        console.print(f"[yellow]Dry run:[/yellow] would set timelog file path to `{timelog_name}`.")
        if selected:
            console.print(f"[yellow]Dry run:[/yellow] would write {len(selected)} selected repos to {GITTAN_SCOPE_FILE}.")
        elif scope_mode.startswith("Only selected"):
            console.print(f"[yellow]Dry run:[/yellow] would write empty allowlist to {GITTAN_SCOPE_FILE} (no repos selected).")
        else:
            console.print("[yellow]Dry run:[/yellow] would configure scope for all git repositories.")
        return

    GITTAN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    GITTAN_FILENAME_FILE.write_text(timelog_name + "\n", encoding="utf-8")
    if selected:
        GITTAN_SCOPE_FILE.write_text("\n".join(selected) + "\n", encoding="utf-8")
    elif scope_mode.startswith("Only selected"):
        # Empty selection explicitly means no repos - write empty file
        GITTAN_SCOPE_FILE.write_text("", encoding="utf-8")
    elif GITTAN_SCOPE_FILE.exists():
        GITTAN_SCOPE_FILE.unlink()


def run_global_timelog_setup(console, *, yes: bool, dry_run: bool) -> None:
    from rich.table import Table

    home = Path.home()
    hooks_dir = home / ".githooks"
    hook_path = hooks_dir / "post-commit"
    ignore_path = home / ".gitignore_global"
    current_hooks_path = _read_global_git_config("core.hooksPath")
    current_excludes_file = _read_global_git_config("core.excludesFile")

    console.print("[bold cyan]Global timelog automation setup[/bold cyan]")
    console.print("This will configure global git hooks so each commit appends an entry to repo-local `TIMELOG.md`.")
    table = Table(title="Current global git status")
    table.add_column("Setting", style="cyan")
    table.add_column("Current value", style="dim")
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
    console.print("\nReference: `GLOBAL_TIMELOG_AUTOMATION.md`")


def _ensure_minimal_projects_config(console, *, yes: bool, dry_run: bool) -> str:
    config_path = Path.cwd() / "timelog_projects.json"
    if config_path.exists():
        try:
            current_payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current_payload = None
        if _looks_like_projects_config(current_payload):
            console.print(f"[green]Project config exists:[/green] {config_path}")
            return "PASS (dry-run)" if dry_run else "PASS"
        console.print(f"[yellow]Project config looks invalid:[/yellow] {config_path}")
        should_repair = yes or questionary.confirm(
            f"Backup and recreate minimal project config at {config_path}?",
            default=False,
        ).ask()
        if not should_repair:
            console.print("[yellow]Keeping current project config unchanged.[/yellow]")
            return "ACTION_REQUIRED"
        backup_path = _timestamped_backup_path(config_path)
        if dry_run:
            console.print(f"[yellow]Dry run:[/yellow] would create backup {backup_path}")
            console.print(f"[yellow]Dry run:[/yellow] would recreate {config_path}")
            return "PASS (dry-run)"
        shutil.copy2(config_path, backup_path)
        console.print(f"[green]Created backup:[/green] {backup_path}")
    should_create = yes or questionary.confirm(f"Create minimal project config at {config_path}?", default=True).ask()
    if not should_create:
        console.print("[yellow]Skipped project config bootstrap.[/yellow]")
        return "SKIPPED"
    project_name, customer, keywords = "default-project", "Default Customer", "default"
    if not yes:
        project_name = questionary.text("Project name:", default=project_name).ask() or project_name
        customer = questionary.text("Customer name:", default=customer).ask() or customer
        keywords = questionary.text("Match terms (comma separated):", default=keywords).ask() or keywords
    payload = {
        "worklog": "TIMELOG.md",
        "projects": [{"name": project_name, "customer": customer, "match_terms": [k.strip() for k in keywords.split(",") if k.strip()], "tracked_urls": [], "email": "", "invoice_title": "", "invoice_description": "", "enabled": True}],
    }
    if dry_run:
        console.print(f"[yellow]Dry run:[/yellow] would create {config_path}")
        return "PASS (dry-run)"
    config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(f"[green]Created minimal project config:[/green] {config_path}")
    return "PASS"


def _print_environment_status(console) -> None:
    from rich.table import Table

    table = Table(title="Environment checks")
    table.add_column("Check", style="cyan")
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


def _run_doctor_check(console, *, dry_run: bool) -> str:
    if dry_run:
        console.print("[yellow]Dry run:[/yellow] would run `gittan doctor`.")
        return "PASS (dry-run)"
    entry = REPO_ROOT / "timelog_extract.py"
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


def run_setup_wizard(console, *, yes: bool, dry_run: bool, skip_smoke: bool) -> None:
    from rich.table import Table

    console.print("[bold cyan]Gittan setup wizard[/bold cyan]")
    console.print("Guided onboarding for local-first timelog reporting.\n")
    summary_rows: list[tuple[str, str, str]] = []
    _print_environment_status(console)
    summary_rows.append(("Environment checks", "PASS", "Printed PATH and optional env status."))
    should_setup_timelog = yes or questionary.confirm("Configure global timelog automation now?", default=True).ask()
    if should_setup_timelog:
        run_global_timelog_setup(console, yes=yes, dry_run=dry_run)
        summary_rows.append(("Global timelog automation", "PASS" if not dry_run else "PASS (dry-run)", "Configured or previewed global hooks + global ignore."))
    else:
        console.print("[yellow]Skipped global timelog automation.[/yellow]")
        summary_rows.append(("Global timelog automation", "SKIPPED", "User skipped this step."))
    projects_status = _ensure_minimal_projects_config(console, yes=yes, dry_run=dry_run)
    summary_rows.append(("Project config bootstrap", projects_status, "Checked existing config and offered minimal bootstrap."))
    doctor_status = _run_doctor_check(console, dry_run=dry_run)
    summary_rows.append(("Doctor check", doctor_status, "Ran (or previewed) source/permission diagnostics."))
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
    summary_table = Table(title="Setup summary")
    summary_table.add_column("Step", style="cyan")
    summary_table.add_column("Result")
    summary_table.add_column("Notes", style="dim")
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
    console.print("\n[green]Setup wizard completed.[/green]")
    console.print("\n[bold cyan]→ First report:[/bold cyan] [bold]gittan report --today --source-summary[/bold]")
    console.print("[dim]Run from a git repository to see your first time estimate.[/dim]")