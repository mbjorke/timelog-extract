"""Doctor table rows for projects-config lint warnings."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.table import Table

from core.config import load_projects_config_payload
from core.projects_lint import lint_projects_payload

_LOG = logging.getLogger(__name__)


# Config-integrity codes that must surface in doctor (vs. the broad-tracked-url
# row). Duplicate/conflicting profiles mis-bucket hours at invoice time.
_INTEGRITY_CODES = frozenset({"slug-customer-conflict", "thin-slug-duplicate"})


def _add_lint_rows_for_codes(
    table: Table,
    config_path: Path,
    codes: frozenset[str],
    *,
    warn_icon: str,
    style_muted: str,
) -> None:
    """Add a doctor row per lint warning whose code is in ``codes``."""
    try:
        payload = load_projects_config_payload(config_path)
    except Exception as exc:
        _LOG.debug("projects lint skipped during doctor: %s", exc)
        return
    for warning in lint_projects_payload(payload):
        if warning.code not in codes:
            continue
        table.add_row(
            "Projects config",
            warn_icon,
            f"[{style_muted}]{warning.message}[/{style_muted}]",
        )


def add_broad_tracked_url_lint_rows(
    table: Table,
    config_path: Path,
    *,
    warn_icon: str,
    style_muted: str,
) -> None:
    _add_lint_rows_for_codes(
        table, config_path, frozenset({"broad-tracked-url"}),
        warn_icon=warn_icon, style_muted=style_muted,
    )


def add_config_integrity_rows(
    table: Table,
    config_path: Path,
    *,
    warn_icon: str,
    style_muted: str,
) -> None:
    """Add doctor rows for project-config integrity warnings (duplicate/conflicting profiles)."""
    _add_lint_rows_for_codes(
        table, config_path, _INTEGRITY_CODES,
        warn_icon=warn_icon, style_muted=style_muted,
    )
