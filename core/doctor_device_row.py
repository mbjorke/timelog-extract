"""Doctor table row for per-device evidence coverage.

The shadow-log row answers "is capture running here?". It cannot answer "is a
device you also work on no longer reporting?" — and that is the failure this row
exists for: work moved to a phone or a cloud session, that device stopped
reaching the ledger, and nothing said so because the machine you *are* on kept
capturing normally.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from rich.table import Table

#: A device quieter than this is called out. Long enough to survive a weekend
#: and a short trip; short enough that a month of lost evidence cannot hide.
STALE_AFTER_DAYS = 10


def _days_since(observed_at: Optional[str], today: date) -> Optional[int]:
    if not observed_at:
        return None
    try:
        parsed = datetime.fromisoformat(str(observed_at))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (today - parsed.date()).days


def describe_devices(
    per_device: Dict[str, Dict[str, Any]], today: date
) -> tuple[list[str], list[str]]:
    """Return (descriptions, stale device names), ordered most recent first."""
    rows: list[tuple[int, str, str]] = []
    stale: list[str] = []
    for device, info in per_device.items():
        gap = _days_since(info.get("last_observed_at"), today)
        if gap is None:
            label = f"{device}: unknown"
            rows.append((10**6, device, label))
            stale.append(device)
            continue
        if gap <= 0:
            when = "today"
        elif gap == 1:
            when = "yesterday"
        else:
            when = f"{gap}d ago"
        rows.append((gap, device, f"{device}: {when}"))
        if gap > STALE_AFTER_DAYS:
            stale.append(device)
    rows.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in rows], stale


def add_device_coverage_row(
    table: Table,
    config_path: Path,
    *,
    ok_icon: str,
    warn_icon: str,
    style_muted: str,
    home: Optional[Path] = None,
    today: Optional[date] = None,
) -> None:
    """Surface which devices are reaching the evidence ledger, and when last."""
    from core.evidence_store import shadow_log_config_setting, store_health

    if shadow_log_config_setting(config_path) != "on":
        return  # the shadow-log row already explains the off state.

    health = store_health(home=home)
    per_device = health.get("per_device") or {}
    if not per_device:
        table.add_row(
            "Device coverage",
            warn_icon,
            f"[{style_muted}]No device-tagged evidence yet. Run `gittan capture` on each "
            f"machine you work from (see docs/runbooks/device-session-capture.md).[/{style_muted}]",
        )
        return

    descriptions, stale = describe_devices(per_device, today or datetime.now(timezone.utc).date())
    detail = " · ".join(descriptions)
    if stale:
        table.add_row(
            "Device coverage",
            warn_icon,
            f"[{style_muted}]{detail} — quiet for over {STALE_AFTER_DAYS} days: "
            f"{', '.join(stale)}. Capture there, or import its export.[/{style_muted}]",
        )
        return
    table.add_row("Device coverage", ok_icon, f"[{style_muted}]{detail}[/{style_muted}]")
