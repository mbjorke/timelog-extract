"""Collector for stock Visual Studio Code activity.

Reads macOS application-support data for:

- ``Code`` — stable channel
- ``Code - Insiders`` — Insiders channel

Evidence comes from (1) the shared VS Code-fork log scrape and (2) workspace
``chatSessions`` (Copilot / VS Code chat requests) — stock Code logs alone are
thin compared with Cursor's proprietary extension logging.
"""

from __future__ import annotations

from pathlib import Path

from collectors.vscode_chat import collect_vscode_chat_sessions
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
        # Copilot / agent terminal-tool analyzers — they log cwd as file://…
        # and look like project work, but are IDE plumbing (not editing).
        "runinterminaltool",
        "commandlinefilewriteanalyzer",
        "commandlineautoapproveanalyzer",
        # Agent handoff IPC — not editing evidence (often floods when Code has
        # the same repo open as Cursor).
        "agentshandoff",
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
    """Scrape stock VS Code logs and workspace chat sessions into events."""
    base_dirs = vscode_base_dirs(home)
    events = collect_fork_logs(
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
    events.extend(
        collect_vscode_chat_sessions(
            profiles,
            dt_from,
            dt_to,
            home,
            local_tz,
            classify_project,
            make_event,
        )
    )
    return events
