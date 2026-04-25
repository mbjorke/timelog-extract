"""Typer command: apply mobile-sourced triage decisions to project config."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    default_projects_config_option,
    load_projects_config_payload,
    save_projects_config_payload,
)

_VALID_RULE_TYPES = {"tracked_urls", "match_terms"}
_SCHEMA_VERSION = 1


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


@app.command("triage-apply")
def triage_apply(
    input_path: Annotated[
        Optional[str],
        typer.Option("--input", "-i", help="Path to decisions JSON file (or - for stdin)"),
    ] = None,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    allow_create: Annotated[bool, typer.Option(help="Create unknown projects")] = False,
    dry_run: Annotated[bool, typer.Option(help="Print what would be applied; do not write")] = False,
):
    """Apply categorization decisions from mobile to timelog_projects.json."""
    try:
        decisions = _load_decisions(input_path)
    except (ValueError, OSError) as e:
        typer.echo(json.dumps({"error": str(e)}))
        raise typer.Exit(code=1) from e

    config_path = Path(projects_config)
    try:
        payload = load_projects_config_payload(config_path)
    except (OSError, ValueError) as e:
        typer.echo(json.dumps({"error": f"Cannot load config: {e}"}))
        raise typer.Exit(code=1) from e

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
        # match_terms are lowercased downstream; tracked_urls preserve case for paths
        deduped_value = rule_value.lower() if rule_type == "match_terms" else rule_value
        key = (project_name.lower(), rule_type, deduped_value)
        if key in seen:
            continue
        seen.add(key)
        validated.append((project_name, rule_type, rule_value))

    if errors:
        typer.echo(json.dumps({"applied": 0, "skipped": 0, "errors": errors}))
        raise typer.Exit(code=1)

    if dry_run:
        typer.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "would_apply": [
                        {"project_name": pn, "rule_type": rt, "rule_value": rv}
                        for pn, rt, rv in validated
                    ],
                    "skipped": len(decisions) - len(validated),
                    "errors": [],
                }
            )
        )
        return

    applied = 0
    for project_name, rule_type, rule_value in validated:
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

    typer.echo(
        json.dumps(
            {
                "applied": applied,
                "skipped": len(decisions) - applied,
                "errors": [],
            }
        )
    )
