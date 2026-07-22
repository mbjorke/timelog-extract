"""Collector for stock Visual Studio Code activity.

Reads the same VS Code log layout as the forks, under macOS application support:

- ``Code`` — stable channel
- ``Code - Insiders`` — Insiders channel

Parsing/attribution lives in ``collectors.vscode_fork``; this module supplies
base dirs, noise markers, and the display source name **VS Code**.
"""

from __future__ import annotations

from pathlib import Path

from collectors.vscode_fork import collect_fork_logs, make_noise_filter

SOURCE_NAME = "VS Code"

# Stable first; Insiders kept for developers who live on the preview channel.
VSCODE_APP_DIRS = ("Code", "Code - Insiders")

_VSCODE_NOISE = make_noise_filter(
    base_extra=(
        # Extension lifecycle / update churn on window open.
        "extensionservice#_doactivateextension",
        "eager extensions activated",
        "wants api proposal",
        "does not exist. likely",
        "update#setstate",
        "update#islatestversion",
        # Window/git/repository plumbing (not meaningful work evidence).
        "window will load",
        "skipping acquiring lock for",
        "[model][openrepository]",
        "opened repository",
        "bootstrapping repository index",
        # Shell-resolution failures and captured stderr dumps.
        "unable to resolve your shell environment",
        "ptyhost was unable to resolve shell",
        "[stderr]",
    ),
    ultra_strict=(
        # Prefer tagged/phrased signatures over lone tokens like "telemetry"
        # so a path/filename containing that word is not dropped as noise.
        "websocket connected",
        "websocket closed",
        "initialization complete",
        "telemetryservice",
        "[telemetry]",
        "extensionservice#",
        "[vscodediagnosticsexecutor] execute:",
    ),
)


def vscode_base_dirs(home: Path) -> list[Path]:
    """Return stock VS Code application-support directories (stable + Insiders)."""
    support = home / "Library" / "Application Support"
    return [support / name for name in VSCODE_APP_DIRS]


def collect_vscode(
    profiles,
    dt_from,
    dt_to,
    home,
    local_tz,
    classify_project,
    make_event,
    noise_profile: str = "strict",
):
    """Scrape stock VS Code logs into project-attributed events."""
    base_dirs = vscode_base_dirs(home)
    return collect_fork_logs(
        profiles,
        dt_from,
        dt_to,
        home,
        local_tz,
        classify_project,
        make_event,
        source_name=SOURCE_NAME,
        base_dirs=base_dirs,
        noise_fn=_VSCODE_NOISE,
        internal_paths=[str(base) for base in base_dirs],
        noise_profile=noise_profile,
    )
