"""Doctor helpers for CLI path detection and hints."""

from __future__ import annotations

import logging
import os
import shutil
import site
import sys
from pathlib import Path
from rich.table import Table

from outputs.terminal_theme import WARN_ICON, STYLE_MUTED

_DOCTOR_LOG = logging.getLogger(__name__)


def _shell_profile_hint() -> str:
    shell = os.environ.get("SHELL", "").lower()
    if "zsh" in shell:
        return "~/.zshrc"
    if "bash" in shell:
        return "~/.bashrc (or ~/.bash_profile on macOS)"
    return "~/.zshrc or ~/.bashrc"


def _shell_reload_phrase() -> str:
    shell = os.environ.get("SHELL", "").lower()
    if "zsh" in shell:
        return "[bold]source ~/.zshrc[/bold]"
    if "bash" in shell:
        return "[bold]source ~/.bashrc[/bold] (or [bold]source ~/.bash_profile[/bold])"
    return "source your shell startup file ([bold]e.g. ~/.zshrc or ~/.bashrc[/bold])"


def _dir_on_path(bin_dir: Path) -> bool:
    try:
        resolved = os.path.normcase(os.path.normpath(str(bin_dir.expanduser().resolve())))
    except OSError:
        resolved = os.path.normcase(os.path.normpath(str(bin_dir.expanduser())))
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if not p.strip():
            continue
        try:
            if os.path.normcase(os.path.normpath(p)) == resolved:
                return True
        except OSError:
            continue
    return False


def add_cli_path_rows(table: Table, *, home: Path) -> bool:
    """Warn when gittan exists but user script dirs are not on PATH."""
    gittan_exe = shutil.which("gittan")
    if gittan_exe:
        table.add_row("CLI (gittan on PATH)", "✓", f"[{STYLE_MUTED}]{gittan_exe}[/{STYLE_MUTED}]")
        return True
    if sys.platform == "win32":
        table.add_row(
            "CLI (gittan on PATH)",
            WARN_ICON,
            f"[{STYLE_MUTED}]Not on PATH. Add Python [bold]Scripts[/bold] to PATH or use [bold]py -m pip install --user[/bold]; see README.[/{STYLE_MUTED}]",
        )
        return False
    hints: list[str] = []
    profile = _shell_profile_hint()
    try:
        user_bin = Path(site.getuserbase()) / "bin"
        if (user_bin / "gittan").is_file() and not _dir_on_path(user_bin):
            hints.append(
                f"[{STYLE_MUTED}]pip --user: run [bold]export PATH=\"{user_bin}:$PATH\"[/bold] "
                f"(add that line to [bold]{profile}[/bold] so new terminals work).[/{STYLE_MUTED}]"
            )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        _DOCTOR_LOG.warning("doctor: skipped pip --user PATH hint: %s", exc)
    pipx_bin = home / ".local" / "bin"
    reload = _shell_reload_phrase()
    if (pipx_bin / "gittan").is_file() and not _dir_on_path(pipx_bin):
        hints.append(
            f"[{STYLE_MUTED}]pipx: run [bold]pipx ensurepath[/bold], then {reload} "
            f"or open a [bold]new[/bold] terminal ([bold]{pipx_bin}[/bold] must be on PATH).[/{STYLE_MUTED}]"
        )
    detail = (
        " ".join(hints)
        if hints
        else f"[{STYLE_MUTED}]`gittan` not on PATH and no known script in user/bin or pipx. Reinstall with [bold]pipx install timelog-extract[/bold] or see README.[/{STYLE_MUTED}]"
    )
    table.add_row("CLI (gittan on PATH)", WARN_ICON, detail)
    return False

