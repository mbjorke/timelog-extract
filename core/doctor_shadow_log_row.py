"""Doctor table row for evidence shadow-log durability state (GH-274)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.table import Table


def add_shadow_log_row(
    table: Table,
    config_path: Path,
    *,
    ok_icon: str,
    warn_icon: str,
    style_muted: str,
    home: Optional[Path] = None,
) -> None:
    """Surface whether observed evidence is being captured durably.

    Off is a recommendation, not an error: source logs (Cursor/Claude histories,
    browser data) rotate, so without the shadow log old evidence silently decays.
    The store sat empty for months because capture was flag-only (GH-274) — this
    row makes that state visible before months are lost.
    """
    from core.evidence_store import shadow_log_config_setting, store_health

    if shadow_log_config_setting(config_path) == "on":
        health = store_health(home=home)
        detail = (
            f"Shadow log: on (config) — {health.get('total_records', 0)} records, "
            f"last capture {health.get('last_captured_at') or 'never'}"
        )
        if health.get("enabled") and not health.get("chain_ok", True):
            detail += " — chain integrity FAILED (run `gittan evidence`)"
        table.add_row("Evidence store", ok_icon, f"[{style_muted}]{detail}[/{style_muted}]")
        return
    table.add_row(
        "Evidence store",
        warn_icon,
        f"[{style_muted}]Shadow log: off — observed evidence decays as source logs rotate. "
        f'Enable once with "shadow_log": "on" in timelog_projects.json '
        f"(or per run: --shadow-log on).[/{style_muted}]",
    )
