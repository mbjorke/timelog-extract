"""Doctor helpers for CLI path detection and hints."""

from __future__ import annotations

import logging
import os
import shutil
import site
import sys
from pathlib import Path

from rich.table import Table

from outputs.terminal_theme import OK_ICON, STYLE_MUTED, WARN_ICON

_DOCTOR_LOG = logging.getLogger(__name__)

_FIX_SHADOW_CMD = (
    "curl -fsSL https://gittan.sh/install | bash -s -- --fix-shadow"
)


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


def _running_gittan() -> Path | None:
    """Return the gittan script next to the running interpreter, if present."""
    if not sys.executable:
        return None
    # Deliberately not resolved: a venv's python is a symlink to the base
    # interpreter, and resolving it would look for the script in the base
    # install's bin instead of the venv's.
    try:
        bindir = Path(sys.executable).parent
    except (OSError, RuntimeError, ValueError):
        return None
    # Windows installs the launcher as gittan.exe, POSIX as a bare script.
    names = ("gittan.exe", "gittan") if sys.platform == "win32" else ("gittan",)
    for name in names:
        candidate = bindir / name
        if candidate.is_file():
            return candidate
    return None


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def list_gittan_on_path(path_env: str | None = None) -> list[Path]:
    """Return every ``gittan`` executable found on PATH (deduped by realpath)."""
    raw = path_env if path_env is not None else os.environ.get("PATH", "")
    name = "gittan.exe" if sys.platform == "win32" else "gittan"
    found: list[Path] = []
    seen: set[str] = set()
    for part in raw.split(os.pathsep):
        if not part.strip():
            continue
        candidate = Path(part) / name
        if not candidate.is_file():
            continue
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        found.append(candidate)
    return found


def add_cli_path_rows(table: Table, *, home: Path) -> bool:
    """Warn when gittan is missing from PATH or shadowed by another install."""
    path_exe = shutil.which("gittan")
    running = _running_gittan()
    on_path = list_gittan_on_path()

    if running and path_exe:
        path_path = Path(path_exe)
        if not _same_file(path_path, running):
            extras = [
                str(p)
                for p in on_path
                if not _same_file(p, running) and not _same_file(p, path_path)
            ]
            extra_note = f" Also on PATH: {', '.join(extras)}." if extras else ""
            table.add_row(
                "CLI (gittan on PATH)",
                WARN_ICON,
                f"[{STYLE_MUTED}]This process: [bold]{running}[/bold]\n"
                f"Plain [bold]gittan[/bold] resolves to [bold]{path_path}[/bold] "
                f"(older/other install shadows this one).{extra_note}\n"
                f"Fix: [bold]{_FIX_SHADOW_CMD}[/bold] then open a new terminal.[/{STYLE_MUTED}]",
            )
            return False
        detail = f"[{STYLE_MUTED}]{running}[/{STYLE_MUTED}]"
        if len(on_path) > 1:
            others = [str(p) for p in on_path if not _same_file(p, running)]
            detail += (
                f"\n[{STYLE_MUTED}]Also on PATH (unused): {', '.join(others)}. "
                f"Safe to remove with [bold]{_FIX_SHADOW_CMD}[/bold].[/{STYLE_MUTED}]"
            )
            table.add_row("CLI (gittan on PATH)", WARN_ICON, detail)
            return False
        table.add_row("CLI (gittan on PATH)", OK_ICON, detail)
        return True

    if path_exe:
        path_path = Path(path_exe)
        if len(on_path) > 1:
            others = [str(p) for p in on_path[1:]]
            table.add_row(
                "CLI (gittan on PATH)",
                WARN_ICON,
                f"[{STYLE_MUTED}]{path_path}\n"
                f"Additional installs later on PATH: {', '.join(others)}. "
                f"If [bold]gittan -V[/bold] looks stale after upgrading, run "
                f"[bold]{_FIX_SHADOW_CMD}[/bold].[/{STYLE_MUTED}]",
            )
            return False
        table.add_row("CLI (gittan on PATH)", OK_ICON, f"[{STYLE_MUTED}]{path_exe}[/{STYLE_MUTED}]")
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
