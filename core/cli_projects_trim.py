"""Typer commands: projects-trim (remove rules) and projects-anchor (add rules)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from core.anchor_plan import (
    ANCHOR_PLAN_APPLY_MIN_HITS,
    ANCHOR_PLAN_SCHEMA_VERSION,
    is_ephemeral_anchor_kind,
    normalize_anchor_kind,
)
from core.cli_app import app
from core.cli_projects_audit import _load_json_input
from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    default_projects_config_option,
    load_projects_config_payload,
    remove_rule_from_project,
    save_projects_config_payload,
)
from core.projects_audit import TRIM_PLAN_SCHEMA_VERSION
from outputs.terminal_theme import (
    CLR_GREEN,
    CLR_VALUE_ORANGE,
    FAIL_ICON,
    OK_ICON,
    STYLE_DIM,
    STYLE_MUTED,
    WARN_ICON,
)


def _load_trim_decisions(path: Optional[str]) -> list[dict[str, Any]]:
    data = _load_json_input(path, TRIM_PLAN_SCHEMA_VERSION, "trim")
    removals = data.get("removals")
    if not isinstance(removals, list):
        raise ValueError("'removals' must be an array")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(removals):
        if not isinstance(item, dict):
            raise ValueError(f"removals[{idx}] must be an object")
        pn, rt, rv = (
            str(item.get("project_name", "")).strip(),
            str(item.get("rule_type", "")).strip(),
            str(item.get("rule_value", "")).strip(),
        )
        if not pn or not rt or not rv:
            raise ValueError(f"removals[{idx}]: project_name, rule_type, rule_value required")
        if rt not in {"match_terms", "tracked_urls"}:
            raise ValueError(f"removals[{idx}]: invalid rule_type")
        out.append({"project_name": pn, "rule_type": rt, "rule_value": rv})
    return out


@app.command("projects-trim")
def projects_trim(
    projects_config: Annotated[
        str, typer.Option(help="JSON config file")
    ] = default_projects_config_option(),
    input_path: Annotated[
        Optional[str],
        typer.Option("-i", "--input", help="JSON file with removals (use - for stdin)"),
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Print planned removals only; no write")] = False,
) -> None:
    """Remove match_terms / tracked_urls entries using an explicit JSON payload."""
    from rich.console import Console

    console = Console()
    try:
        removals = _load_trim_decisions(input_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        console.print(
            f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Invalid trim input:[/{CLR_VALUE_ORANGE}] {exc}"
        )
        console.print(
            f"[{STYLE_MUTED}]Next: Check the JSON format of your trim plan file.[/{STYLE_MUTED}]"
        )
        raise typer.Exit(code=1) from exc

    if not removals:
        console.print(
            f"{WARN_ICON} [{CLR_VALUE_ORANGE}]No removals in input; nothing to do.[/{CLR_VALUE_ORANGE}]"
        )
        raise typer.Exit(code=0)

    cfg_path = Path(projects_config).expanduser()
    base = load_projects_config_payload(cfg_path)
    work = copy.deepcopy(base) if dry_run else base
    preview: list[str] = []
    for item in removals:
        ok = remove_rule_from_project(
            work,
            project_name=item["project_name"],
            rule_type=item["rule_type"],
            rule_value=item["rule_value"],
        )
        preview.append(
            f"{'remove' if ok else 'skip (not found)'}: {item['project_name']} "
            f"{item['rule_type']}={item['rule_value']!r}"
        )

    console.print("\n".join(preview))
    if dry_run:
        console.print(
            f"{WARN_ICON} [{CLR_VALUE_ORANGE}]Dry run — config not written.[/{CLR_VALUE_ORANGE}]"
        )
        raise typer.Exit(code=0)

    backup = backup_projects_config_if_exists(cfg_path)
    if backup:
        console.print(f"[{STYLE_DIM}]Backup:[/{STYLE_DIM}] {backup}")
    save_projects_config_payload(cfg_path, work)
    console.print(f"{OK_ICON} [{CLR_GREEN}]projects-trim: config updated.[/{CLR_GREEN}]")


def _load_anchor_decisions(path: Optional[str]) -> list[dict[str, Any]]:
    data = _load_json_input(path, ANCHOR_PLAN_SCHEMA_VERSION, "anchor")
    additions = data.get("additions")
    if not isinstance(additions, list):
        raise ValueError("'additions' must be an array")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(additions):
        if not isinstance(item, dict):
            raise ValueError(f"additions[{idx}] must be an object")
        pn, rt, rv = (
            str(item.get("project_name", "")).strip(),
            str(item.get("rule_type", "match_terms")).strip() or "match_terms",
            str(item.get("rule_value", "")).strip(),
        )
        try:
            kind = normalize_anchor_kind(str(item.get("anchor_kind", "")))
        except ValueError as exc:
            raise ValueError(f"additions[{idx}]: {exc}") from exc
        hits_raw = item.get("hits")
        try:
            hits = None if hits_raw in (None, "") else int(hits_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"additions[{idx}]: hits must be an integer") from exc
        if not pn or not rv:
            raise ValueError(f"additions[{idx}]: project_name and rule_value required")
        if rt not in {"match_terms", "tracked_urls"}:
            raise ValueError(f"additions[{idx}]: rule_type must be match_terms or tracked_urls")
        out.append(
            {
                "project_name": pn,
                "rule_type": rt,
                "rule_value": rv,
                "anchor_kind": kind,
                "hits": hits,
            }
        )
    return out


@app.command("projects-anchor")
def projects_anchor(
    projects_config: Annotated[
        str, typer.Option(help="JSON config file")
    ] = default_projects_config_option(),
    input_path: Annotated[
        Optional[str],
        typer.Option("-i", "--input", help="JSON file with additions (use - for stdin)"),
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Print planned additions only; no write")] = False,
    include_ephemeral_kinds: Annotated[
        bool,
        typer.Option(
            "--include-ephemeral-kinds",
            help=(
                "Apply branch/label rows (default: skip them). Prefer attaching repo/dir "
                "to an existing customer/line instead of permanent match_terms from "
                "ephemeral session context."
            ),
        ),
    ] = False,
    min_hits: Annotated[
        int,
        typer.Option(
            "--min-hits",
            help=(
                f"Skip rows whose hits are below this floor when hits are present "
                f"(default {ANCHOR_PLAN_APPLY_MIN_HITS}). Rows without hits still apply."
            ),
        ),
    ] = ANCHOR_PLAN_APPLY_MIN_HITS,
) -> None:
    """Add rules from an anchor plan (stable signals: hosts, repos, dirs by default)."""
    from rich.console import Console

    console = Console()
    try:
        additions = _load_anchor_decisions(input_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        console.print(
            f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Invalid anchor input:[/{CLR_VALUE_ORANGE}] {exc}"
        )
        console.print(
            f"[{STYLE_MUTED}]Next: Check the JSON format of your anchor plan file.[/{STYLE_MUTED}]"
        )
        raise typer.Exit(code=1) from exc

    if not additions:
        console.print(
            f"{WARN_ICON} [{CLR_VALUE_ORANGE}]No additions in input; nothing to do.[/{CLR_VALUE_ORANGE}]"
        )
        raise typer.Exit(code=0)

    floor = max(1, int(min_hits))
    skipped: list[str] = []
    apply_rows: list[dict[str, Any]] = []
    for item in additions:
        kind = item.get("anchor_kind") or ""
        if is_ephemeral_anchor_kind(kind) and not include_ephemeral_kinds:
            skipped.append(
                f"skip ephemeral {kind}: {item['project_name']} "
                f"{item['rule_type']}={item['rule_value']!r}"
            )
            continue
        hits = item.get("hits")
        if hits is not None and int(hits) < floor:
            skipped.append(
                f"skip low-hit ({hits}<{floor}): {item['project_name']} "
                f"{item['rule_type']}={item['rule_value']!r}"
            )
            continue
        apply_rows.append(item)

    if skipped:
        console.print(
            f"[{STYLE_DIM}]skipped {len(skipped)} ephemeral/low-hit candidate(s)[/{STYLE_DIM}]"
        )
    for line in skipped:
        console.print(f"[{STYLE_DIM}]{line}[/{STYLE_DIM}]")

    if not apply_rows:
        console.print(
            f"{WARN_ICON} [{CLR_VALUE_ORANGE}]No apply candidates left "
            "(plan was only ephemeral/low-hit rows, or empty after filter).[/{CLR_VALUE_ORANGE}]"
        )
        console.print(
            f"[{STYLE_MUTED}]Next: Re-run with --include-ephemeral-kinds and/or a lower --min-hits only if "
            "you intentionally want those rows as permanent rules.[/{STYLE_MUTED}]"
        )
        raise typer.Exit(code=1)

    cfg_path = Path(projects_config).expanduser()
    base = load_projects_config_payload(cfg_path)
    work = copy.deepcopy(base) if dry_run else base
    preview: list[str] = []
    for item in apply_rows:
        _rt, _rv, created = apply_rule_to_project(
            work,
            project_name=item["project_name"],
            rule_type=item["rule_type"],
            rule_value=item["rule_value"],
        )
        verb = "add (new project)" if created else "add"
        preview.append(f"{verb}: {item['project_name']} {item['rule_type']}={item['rule_value']!r}")

    console.print("\n".join(preview))
    if dry_run:
        console.print(
            f"{WARN_ICON} [{CLR_VALUE_ORANGE}]Dry run — config not written.[/{CLR_VALUE_ORANGE}]"
        )
        raise typer.Exit(code=0)

    backup = backup_projects_config_if_exists(cfg_path)
    if backup:
        console.print(f"[{STYLE_DIM}]Backup:[/{STYLE_DIM}] {backup}")
    save_projects_config_payload(cfg_path, work)
    console.print(f"{OK_ICON} [{CLR_GREEN}]projects-anchor: config updated.[/{CLR_GREEN}]")
