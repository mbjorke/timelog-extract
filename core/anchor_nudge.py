"""Status-surface anchor nudge: one-line warning + optional interactive mapping.

The status command shows a short warning when activity comes from anchors no
project matches yet — a working directory, git branch, or session title. When
the session is interactive, the user can map them to projects in place
(questionary), which is the medium-weight tier of the modal wall
(docs/ideas/conversational-ui-stack.md). A richer React Ink overlay can replace
this surface later without changing the data contract.
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
from core.projects_audit import ANCHOR_KIND_LABELS

_CREATE_PREFIX = "Create new project: "
_SKIP = "Skip"
_STOP = "Stop mapping"


def _kind_label(kind: str) -> str:
    return ANCHOR_KIND_LABELS.get(str(kind), str(kind) or "anchor")


def status_anchor_line(anchors: list[dict]) -> str | None:
    """One-line status warning for unmapped activity anchors, or None."""
    if not anchors:
        return None
    listed = ", ".join(
        f"{a['value']} ({_kind_label(a.get('kind', ''))}, {a['hits']})" for a in anchors[:3]
    )
    more = "" if len(anchors) <= 3 else f" +{len(anchors) - 3} more"
    plural = "" if len(anchors) == 1 else "s"
    return f"⚠ {len(anchors)} unmapped activity anchor{plural}: {listed}{more}"


def should_prompt() -> bool:
    """Interactive prompts only on a real TTY (never in CI/pipes)."""
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (ValueError, OSError):
        return False


def run_interactive_anchor_flow(
    console,
    anchors: list[dict],
    profiles: list[dict],
    projects_config: str,
) -> int:
    """Map unmapped anchors to projects via questionary; apply with backup.

    Returns the number of match_terms added. Each anchor value (working
    directory, git branch, or session title) becomes a match_term on the chosen
    (or newly created) project. Safe to call only when should_prompt().
    """
    import questionary

    existing = sorted(
        {str(p.get("name", "")).strip() for p in profiles if str(p.get("name", "")).strip()},
        key=str.lower,
    )

    additions: list[tuple[str, str]] = []  # (project_name, anchor_value)
    for entry in anchors:
        value = str(entry.get("value", "")).strip()
        if not value:
            continue
        kind = _kind_label(entry.get("kind", ""))
        choices = [*existing, f"{_CREATE_PREFIX}{value}", _SKIP, _STOP]
        answer = questionary.select(
            f"Map {kind} '{value}' ({entry.get('hits', 0)} events) to project",
            choices=choices,
        ).ask()
        if answer is None or answer == _STOP:
            break
        if answer == _SKIP:
            continue
        target = value if answer == f"{_CREATE_PREFIX}{value}" else answer
        additions.append((target, value))

    if not additions:
        console.print("[dim]No anchors mapped.[/dim]")
        return 0

    cfg_path = Path(projects_config).expanduser()
    payload = load_projects_config_payload(cfg_path)
    for project_name, value in additions:
        apply_rule_to_project(
            payload,
            project_name=project_name,
            rule_type="match_terms",
            rule_value=value,
        )

    backup = backup_projects_config_if_exists(cfg_path)
    if backup:
        console.print(f"[dim]Backup:[/dim] {backup}")
    save_projects_config_payload(cfg_path, payload)
    summary = ", ".join(f"{value}→{name}" for name, value in additions)
    console.print(f"[green]Mapped {len(additions)} anchor(s): {summary}[/green]")
    return len(additions)


def maybe_run_interactive_anchor_mapping(
    console,
    report,
    *,
    projects_config: str | None = None,
) -> bool:
    """Offer to map unanchored dirs/branches/session titles when on a TTY."""
    from core.report_nudges import unanchored_anchors_for_report

    if not should_prompt():
        return False
    anchors = unanchored_anchors_for_report(report)
    if not anchors:
        return False

    import questionary

    line = status_anchor_line(anchors)
    if line:
        console.print(line)
    if not questionary.confirm(
        "Map activity anchors (working dirs, branches, session titles) to projects?",
        default=True,
    ).ask():
        console.print("[dim]Skipped — run `gittan map` anytime to map anchors.[/dim]")
        return False

    config = str(
        projects_config
        or getattr(report, "config_path", None)
        or getattr(getattr(report, "args", None), "projects_config", "")
        or ""
    ).strip()
    if not config:
        console.print("[dim]No projects config path — cannot save anchor mappings.[/dim]")
        return False

    applied = run_interactive_anchor_flow(
        console,
        anchors,
        list(getattr(report, "profiles", []) or []),
        config,
    )
    if applied:
        console.print("[dim]Re-run the same report to see updated project hours.[/dim]")
    return applied > 0
