"""Doctor table rows for projects-config lint warnings."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.table import Table

from core.config import load_projects_config_payload
from core.projects_lint import lint_projects_payload

_LOG = logging.getLogger(__name__)

# Lint codes surfaced as doctor rows: over-broad tracked_urls plus the config
# integrity codes (duplicate/conflicting profiles mis-bucket hours at invoice time).
_DOCTOR_LINT_CODES = frozenset(
    {"broad-tracked-url", "slug-customer-conflict", "thin-slug-duplicate"}
)


def add_projects_config_lint_rows(
    table: Table,
    config_path: Path,
    *,
    warn_icon: str,
    style_muted: str,
) -> None:
    """Load and lint the projects config once, adding a doctor row per surfaced warning."""
    try:
        payload = load_projects_config_payload(config_path)
    except (OSError, ValueError) as exc:  # malformed JSON is a ValueError subclass
        _LOG.debug("projects lint skipped during doctor: %s", exc)
        return
    for warning in lint_projects_payload(payload):
        if warning.code not in _DOCTOR_LINT_CODES:
            continue
        table.add_row(
            "Projects config",
            warn_icon,
            f"[{style_muted}]{warning.message}[/{style_muted}]",
        )
