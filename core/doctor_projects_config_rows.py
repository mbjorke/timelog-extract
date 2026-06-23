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
