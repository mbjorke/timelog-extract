"""Doctor rows for per-source liveness (GH-366).

"Logs readable" proves reachability, not liveness — twice (#345, #363) a source
went silent while doctor stayed green. These rows show, per source, when it last
produced evidence and on how many recent days, from the shadow evidence log.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from core.source_liveness import (
    LOOKBACK_DAYS,
    MAX_SILENT_GAP_DAYS,
    shadow_baseline_by_source,
)


def add_source_liveness_rows(
    table: Any,
    *,
    home: Optional[Path] = None,
    ok_icon: str,
    warn_icon: str,
    na_icon: str,
    style_muted: str,
    today: Optional[date] = None,
) -> None:
    """Add one liveness row per recently active source (distinct from readability)."""
    today = today or date.today()
    # End tomorrow so today's records count; lookback=LOOKBACK_DAYS keeps a true
    # N-day window ([today-(N-1), tomorrow) ≡ N calendar days including today).
    baseline = shadow_baseline_by_source(
        today + timedelta(days=1), home=home, lookback_days=LOOKBACK_DAYS
    )
    if not baseline:
        table.add_row(
            "Source liveness",
            na_icon,
            f"[{style_muted}]No shadow-log history — enable \"shadow_log\": \"on\" in "
            f"timelog_projects.json to track per-source liveness.[/{style_muted}]",
        )
        return
    stale_floor = (today - timedelta(days=MAX_SILENT_GAP_DAYS)).isoformat()
    for source in sorted(baseline):
        info = baseline[source]
        icon = ok_icon if info["last_active"] >= stale_floor else warn_icon
        # Label stays the plain source name (keeps the table column narrow);
        # the "Liveness:" prefix in the detail distinguishes it from the
        # readability row for the same source.
        detail = (
            f"Liveness: last event {info['last_active']} — active "
            f"{info['days_active']} of the last {LOOKBACK_DAYS} days"
        )
        if icon == warn_icon:
            detail += " — previously active source has gone quiet"
        table.add_row(
            source,
            icon,
            f"[{style_muted}]{detail}[/{style_muted}]",
        )
