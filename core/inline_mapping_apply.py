"""Interactive apply loop for inline mapping suggestions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import typer

from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    load_projects_config_payload,
    remove_rule_from_project,
    save_projects_config_payload,
)
from core.projects_audit import build_inline_mapping_candidates


def _is_interactive_terminal() -> bool:
    return bool(getattr(sys.stdin, "isatty", lambda: False)() and getattr(sys.stdout, "isatty", lambda: False)())


def _pick_project(known_projects: list[str], *, prompt: str) -> str | None:
    if not known_projects:
        return None
    for index, name in enumerate(known_projects, start=1):
        print(f"  {index}) {name}")
    print("  0) Skip")
    choice = typer.prompt(prompt, default="0")
    if str(choice).strip() in {"", "0"}:
        return None
    try:
        selected = int(str(choice).strip())
    except ValueError:
        return None
    if selected < 1 or selected > len(known_projects):
        return None
    return known_projects[selected - 1]


def run_inline_mapping_apply_loop(
    *,
    events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    projects_config: str,
    max_candidates: int = 3,
    interactive: bool | None = None,
) -> None:
    candidates = build_inline_mapping_candidates(
        events=events,
        profiles=profiles,
        max_candidates=max_candidates,
    )
    if not candidates:
        return

    if interactive is None:
        interactive = _is_interactive_terminal()
    if not interactive:
        print("Mapping suggestions: non-interactive mode, no changes applied.")
        return

    known_projects = sorted(
        {str(p.get("name", "")).strip() for p in profiles if str(p.get("name", "")).strip()},
        key=str.lower,
    )
    cfg_path = Path(str(projects_config)).expanduser()
    plan: list[dict[str, str]] = []

    try:
        for candidate in candidates:
            kind = str(candidate.get("kind", "")).strip()
            if kind == "host":
                host = str(candidate.get("host", "")).strip()
                hits = int(candidate.get("hits", 0))
                if not host:
                    continue
                question = f"Apply host suggestion '{host}' ({hits} hits)?"
                if not typer.confirm(question, default=False):
                    continue
                project_name = _pick_project(known_projects, prompt="Select target project number")
                if not project_name:
                    continue
                plan.append(
                    {
                        "action": "add",
                        "project_name": project_name,
                        "rule_type": "tracked_urls",
                        "rule_value": host,
                    }
                )
                continue

            if kind == "stale_term":
                project_name = str(candidate.get("project_name", "")).strip()
                rule_type = str(candidate.get("rule_type", "")).strip() or "match_terms"
                rule_value = str(candidate.get("rule_value", "")).strip()
                if not project_name or not rule_value:
                    continue
                question = f"Apply stale-term suggestion for '{project_name}' term '{rule_value}'?"
                if not typer.confirm(question, default=False):
                    continue
                move = typer.confirm("Move to another project? (No = remove)", default=False)
                if move:
                    target_project = _pick_project(
                        [name for name in known_projects if name.lower() != project_name.lower()],
                        prompt="Select move target project number",
                    )
                    if target_project:
                        plan.append(
                            {
                                "action": "move",
                                "project_name": project_name,
                                "target_project": target_project,
                                "rule_type": rule_type,
                                "rule_value": rule_value,
                            }
                        )
                    continue
                plan.append(
                    {
                        "action": "remove",
                        "project_name": project_name,
                        "rule_type": rule_type,
                        "rule_value": rule_value,
                    }
                )
    except (typer.Abort, EOFError, KeyboardInterrupt):
        print("Mapping suggestions: prompt aborted, no changes applied.")
        return

    if not plan:
        print("Mapping suggestions: no changes planned.")
        return

    payload = load_projects_config_payload(cfg_path)
    for step in plan:
        action = step["action"]
        if action == "add":
            apply_rule_to_project(
                payload,
                project_name=step["project_name"],
                rule_type=step["rule_type"],
                rule_value=step["rule_value"],
            )
            continue
        if action == "remove":
            remove_rule_from_project(
                payload,
                project_name=step["project_name"],
                rule_type=step["rule_type"],
                rule_value=step["rule_value"],
            )
            continue
        if action == "move":
            removed = remove_rule_from_project(
                payload,
                project_name=step["project_name"],
                rule_type=step["rule_type"],
                rule_value=step["rule_value"],
            )
            if removed:
                apply_rule_to_project(
                    payload,
                    project_name=step["target_project"],
                    rule_type=step["rule_type"],
                    rule_value=step["rule_value"],
                )

    backup = backup_projects_config_if_exists(cfg_path)
    save_projects_config_payload(cfg_path, payload)
    backup_note = f" (backup: {backup})" if backup else ""
    print(f"Mapping suggestions applied: {len(plan)} change(s){backup_note}.")
