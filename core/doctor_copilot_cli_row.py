"""Doctor health-check row for GitHub Copilot CLI local directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from collectors.copilot_cli import copilot_cli_data_dir


def add_copilot_cli_doctor_row(
    table: Any,
    home: Path,
    *,
    ok_icon: str,
    warn_icon: str,
    na_icon: str,
    style_muted: str,
) -> None:
    cc_root = copilot_cli_data_dir(home)
    cc_logs = cc_root / "logs"
    if not cc_root.exists():
        table.add_row(
            "GitHub Copilot CLI",
            na_icon,
            f"[{style_muted}]No data directory yet ({cc_root}); appears after Copilot CLI use.[/{style_muted}]",
        )
        return
    if cc_logs.is_dir():
        try:
            has_logs = any(cc_logs.glob("*.log"))
        except OSError:
            has_logs = False
        if has_logs:
            table.add_row(
                "GitHub Copilot CLI",
                ok_icon,
                f"[{style_muted}]Logs readable under {cc_logs}[/{style_muted}]",
            )
        else:
            table.add_row(
                "GitHub Copilot CLI",
                warn_icon,
                f"[{style_muted}]{cc_root} exists but no *.log in logs/ yet.[/{style_muted}]",
            )
        return
    table.add_row(
        "GitHub Copilot CLI",
        warn_icon,
        f"[{style_muted}]{cc_root} exists but logs/ missing.[/{style_muted}]",
    )
