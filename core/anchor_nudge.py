"""Status-surface anchor nudge: one-line warning + optional interactive mapping.

The status command shows a short warning when activity comes from working
directories no project matches yet. When the session is interactive, the user
can map them to projects in place (questionary), which is the medium-weight tier
of the modal wall (docs/ideas/conversational-ui-stack.md). A richer React Ink
overlay can replace this surface later without changing the data contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    load_projects_config_payload,
    save_projects_config_payload,
)

_CREATE_PREFIX = "Create new project: "
_SKIP = "Skip"
_STOP = "Stop mapping"


def status_anchor_line(dirs: list[dict]) -> str | None:
    """One-line status warning for unmapped working directories, or None."""
    if not dirs:
        return None
    listed = ", ".join(f"{d['dir']} ({d['hits']})" for d in dirs[:3])
    more = "" if len(dirs) <= 3 else f" +{len(dirs) - 3} more"
    plural = "y" if len(dirs) == 1 else "ies"
    return f"⚠ {len(dirs)} unmapped working director{plural}: {listed}{more}"


def should_prompt() -> bool:
    """Interactive prompts only on a real TTY (never in CI/pipes)."""
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (ValueError, OSError):
        return False


def run_interactive_anchor_flow(
    console,
    dirs: list[dict],
    profiles: list[dict],
    projects_config: str,
) -> int:
    """Map unmapped directories to projects via questionary; apply with backup.

    Returns the number of match_terms added. Each directory becomes a match_term
    on the chosen (or newly created) project. Safe to call only when should_prompt().
    """
    import questionary

    existing = sorted(
        {str(p.get("name", "")).strip() for p in profiles if str(p.get("name", "")).strip()},
        key=str.lower,
    )

    additions: list[tuple[str, str]] = []  # (project_name, dir_leaf)
    for entry in dirs:
        leaf = str(entry.get("dir", "")).strip()
        if not leaf:
            continue
        choices = [*existing, f"{_CREATE_PREFIX}{leaf}", _SKIP, _STOP]
        answer = questionary.select(
            f"Map directory '{leaf}' ({entry.get('hits', 0)} events) to project",
            choices=choices,
        ).ask()
        if answer is None or answer == _STOP:
            break
        if answer == _SKIP:
            continue
        target = leaf if answer == f"{_CREATE_PREFIX}{leaf}" else answer
        additions.append((target, leaf))

    if not additions:
        console.print("[dim]No directories mapped.[/dim]")
        return 0

    cfg_path = Path(projects_config).expanduser()
    payload = load_projects_config_payload(cfg_path)
    for project_name, leaf in additions:
        apply_rule_to_project(
            payload,
            project_name=project_name,
            rule_type="match_terms",
            rule_value=leaf,
        )

    backup = backup_projects_config_if_exists(cfg_path)
    if backup:
        console.print(f"[dim]Backup:[/dim] {backup}")
    save_projects_config_payload(cfg_path, payload)
    summary = ", ".join(f"{leaf}→{name}" for name, leaf in additions)
    console.print(f"[green]Mapped {len(additions)} director(y/ies): {summary}[/green]")
    return len(additions)
