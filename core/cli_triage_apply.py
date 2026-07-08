"""Typer command: apply mobile-sourced triage decisions to project config."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import questionary

from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    load_projects_config_payload,
    save_projects_config_payload,
)
from core.triage_domain_signals import is_generic_triage_domain

_VALID_RULE_TYPES = {"tracked_urls", "match_terms"}
_SCHEMA_VERSION = 1


def _decision_payload(project_name: str, rule_type: str, rule_value: str) -> dict[str, str]:
    return {
        "project_name": project_name,
        "rule_type": rule_type,
        "rule_value": rule_value,
    }


def _load_decisions(input_path: Optional[str]) -> list[dict]:
    if input_path and input_path != "-":
        text = Path(input_path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object with a 'decisions' key")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("'decisions' must be a JSON array")
    return decisions


def _validate_decision(d: object, idx: int) -> tuple[str, str, str]:
    if not isinstance(d, dict):
        raise ValueError(f"Decision #{idx}: must be a JSON object")
    project_name = str(d.get("project_name", "")).strip()
    rule_type = str(d.get("rule_type", "")).strip()
    rule_value = str(d.get("rule_value", "")).strip()
    for field, val in (("project_name", project_name), ("rule_type", rule_type), ("rule_value", rule_value)):
        if not val:
            raise ValueError(f"Decision #{idx}: missing required field '{field}'")
    if rule_type not in _VALID_RULE_TYPES:
        raise ValueError(
            f"Decision #{idx}: rule_type '{rule_type}' must be one of {sorted(_VALID_RULE_TYPES)}"
        )
    return project_name, rule_type, rule_value


def _project_exists(payload: dict, project_name: str) -> bool:
    clean = project_name.strip().lower()
    for p in payload.get("projects", []):
        if str(p.get("name", "")).strip().lower() == clean:
            return True
    return False


def _is_auto_disallowed_tracked_url(rule_type: str, rule_value: str) -> bool:
    if rule_type != "tracked_urls":
        return False
    candidate = str(rule_value or "").strip().lower()
    if not candidate:
        return False
    # Guard auto-apply flows from adding broad generic roots;
    # manual config edits remain fully supported.
    return is_generic_triage_domain(candidate)


def _render_plan_preview(validated: list[tuple[str, str, str]]) -> str:
    if not validated:
        return "No validated decisions."
    by_project: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for project_name, rule_type, rule_value in validated:
        by_project[project_name].append((rule_type, rule_value))
    lines = ["Planned config updates:"]
    for project_name in sorted(by_project.keys(), key=str.lower):
        lines.append(f"  {project_name}:")
        for rule_type, rule_value in by_project[project_name]:
            lines.append(f"    + {rule_type}: {rule_value}")
    return "\n".join(lines)


def _interactive_review(validated: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    if not validated:
        return []
    selected: list[tuple[str, str, str]] = []
    for project_name, rule_type, rule_value in validated:
        keep = questionary.confirm(
            f"Apply {rule_type}='{rule_value}' to project '{project_name}'?",
            default=True,
        ).ask()
        if keep:
            selected.append((project_name, rule_type, rule_value))
    return selected


def apply_triage_decisions_payload(
    *,
    decisions: list[dict],
    projects_config: str,
    allow_create: bool = False,
    dry_run: bool = False,
    interactive_review: bool = False,
) -> dict:
    config_path = Path(projects_config)
    payload = load_projects_config_payload(config_path)

    seen: set[tuple[str, str, str]] = set()
    validated: list[tuple[str, str, str]] = []
    errors: list[str] = []

    for idx, d in enumerate(decisions):
        try:
            project_name, rule_type, rule_value = _validate_decision(d, idx)
        except ValueError as e:
            errors.append(str(e))
            continue
        if not allow_create and not _project_exists(payload, project_name):
            errors.append(
                f"Decision #{idx}: project '{project_name}' not in config (use --allow-create to create)"
            )
            continue
        if _is_auto_disallowed_tracked_url(rule_type, rule_value):
            continue
        deduped_value = rule_value.lower() if rule_type == "match_terms" else rule_value
        key = (project_name.lower(), rule_type, deduped_value)
        if key in seen:
            continue
        seen.add(key)
        validated.append((project_name, rule_type, rule_value))

    if errors:
        return {"applied": 0, "skipped": 0, "errors": errors}

    selected = list(validated)
    if interactive_review:
        selected = _interactive_review(validated)

    if dry_run:
        return {
            "dry_run": True,
            "preview": _render_plan_preview(selected),
            "would_apply": [_decision_payload(pn, rt, rv) for pn, rt, rv in selected],
            "skipped": len(decisions) - len(selected),
            "errors": [],
        }

    applied = 0
    if not selected:
        return {"applied": 0, "skipped": len(decisions), "errors": []}

    for project_name, rule_type, rule_value in selected:
        apply_rule_to_project(
            payload,
            project_name=project_name,
            rule_type=rule_type,
            rule_value=rule_value,
        )
        applied += 1

    if applied:
        backup_projects_config_if_exists(config_path)
        save_projects_config_payload(config_path, payload)

    return {
        "applied": applied,
        "skipped": len(decisions) - len(selected),
        "preview": _render_plan_preview(selected),
        "errors": [],
    }


