"""Anchor-plan builder + GH-342 apply guardrails (inventory vs apply)."""

from __future__ import annotations

from typing import Any

from core.projects_audit import (
    AUDIT_SCHEMA_VERSION,
    SIGNAL_RULE_TYPE,
)

ANCHOR_PLAN_SCHEMA_VERSION = 1

# branch/label are inventory, not default apply targets. Repo/dir/host may become
# permanent rules; feature branches and session titles must not (GH-342).
EPHEMERAL_ANCHOR_KINDS = frozenset({"branch", "label"})
# Default floor for apply candidates — matches UNANCHORED_ANCHOR_NUDGE_MIN_HITS.
ANCHOR_PLAN_APPLY_MIN_HITS = 20


def is_ephemeral_anchor_kind(kind: str) -> bool:
    """True for branch/label — session context, not default match_terms material."""
    return str(kind or "").strip().lower() in EPHEMERAL_ANCHOR_KINDS


def build_anchor_plan_from_audit(
    audit_payload: dict[str, Any],
    *,
    min_hits: int = ANCHOR_PLAN_APPLY_MIN_HITS,
    include_ephemeral_kinds: bool = False,
) -> dict[str, Any]:
    """Build a `projects-anchor` plan (schema v1): rule additions from signals.

    Default apply candidates are **stable** unanchored signals only (`host` →
    tracked_urls; `repo` / `dir` → match_terms) at ``min_hits`` (default
    :data:`ANCHOR_PLAN_APPLY_MIN_HITS`). Ephemeral kinds (`branch`, `label`) go
    to ``inventory`` unless ``include_ephemeral_kinds`` is true — they are
    session context, not permanent config (GH-342).

    Each apply row carries ``rule_type`` / ``anchor_kind``; ``project_name``
    defaults to the signal value — edit it to target an existing project before
    applying. ``gittan projects-anchor`` creates a new project if the name does
    not exist.
    """
    sv = int(audit_payload.get("schema_version", 0))
    if sv != AUDIT_SCHEMA_VERSION:
        raise ValueError(f"audit schema_version must be {AUDIT_SCHEMA_VERSION}, got {sv}")

    floor = max(1, int(min_hits))
    additions: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for row in audit_payload.get("top_signals") or []:
        if row.get("anchored"):
            continue
        value = str(row.get("value", "")).strip()
        hits = int(row.get("hits", 0))
        if not value or hits < floor:
            continue
        kind = str(row.get("kind", ""))
        entry = {
            "project_name": value,
            "rule_type": str(row.get("rule_type") or SIGNAL_RULE_TYPE.get(kind, "match_terms")),
            "rule_value": value,
            "anchor_kind": kind,
            "hits": hits,
        }
        if is_ephemeral_anchor_kind(kind) and not include_ephemeral_kinds:
            inventory.append(entry)
            continue
        additions.append(entry)

    note = (
        "Apply candidates are stable unanchored signals only (host → tracked_urls; "
        "repo/dir → match_terms) at min_hits. branch/label stay under inventory "
        "(session context — not default match_terms) unless the plan was built with "
        "--include-ephemeral-kinds. project_name defaults to the signal value — edit "
        "it to map to an existing project. Apply: gittan projects-anchor -i <file> "
        "--dry-run then rerun without --dry-run."
    )

    return {
        "schema_version": ANCHOR_PLAN_SCHEMA_VERSION,
        "note": note,
        "additions": additions,
        "inventory": inventory,
        "meta": {
            "source_audit_command": audit_payload.get("command", "gittan projects-audit"),
            "audit_options": audit_payload.get("options", {}),
            "min_hits": floor,
            "anchor_candidates": len(additions),
            "inventory_candidates": len(inventory),
            "include_ephemeral_kinds": bool(include_ephemeral_kinds),
            "ephemeral_kinds_excluded_from_apply": sorted(EPHEMERAL_ANCHOR_KINDS),
            "default_apply_kinds": ["host", "repo", "dir"],
        },
    }
