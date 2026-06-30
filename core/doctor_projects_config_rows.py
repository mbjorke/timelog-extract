"""Doctor table rows for projects-config lint warnings."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.table import Table

from core.config import load_projects_config_payload
from core.projects_lint import lint_projects_payload

_LOG = logging.getLogger(__name__)


def add_broad_tracked_url_lint_rows(
    table: Table,
    config_path: Path,
    *,
    warn_icon: str,
    style_muted: str,
) -> None:
    try:
        payload = load_projects_config_payload(config_path)
    except Exception as exc:
        _LOG.debug("projects lint skipped during doctor: %s", exc)
        return
    for warning in lint_projects_payload(payload):
        if warning.code != "broad-tracked-url":
            continue
        table.add_row(
            "Projects config",
            warn_icon,
            f"[{style_muted}]{warning.message}[/{style_muted}]",
        )


# Config-integrity codes that must surface in doctor (vs. the broad-tracked-url
# row above). Duplicate/conflicting profiles mis-bucket hours at invoice time.
_INTEGRITY_CODES = frozenset({"slug-customer-conflict", "thin-slug-duplicate"})


def add_config_integrity_rows(
    table: Table,
    config_path: Path,
    *,
    warn_icon: str,
    style_muted: str,
) -> None:
    """Add doctor rows for project-config integrity warnings (duplicate/conflicting profiles)."""
    try:
        payload = load_projects_config_payload(config_path)
    except Exception as exc:
        _LOG.debug("config integrity lint skipped during doctor: %s", exc)
        return
    for warning in lint_projects_payload(payload):
        if warning.code not in _INTEGRITY_CODES:
            continue
        table.add_row(
            "Projects config",
            warn_icon,
            f"[{style_muted}]{warning.message}[/{style_muted}]",
        )
