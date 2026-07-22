"""Collector for Devin Desktop (formerly Windsurf) IDE activity.

Cognition rebranded Windsurf to Devin Desktop (2026). The app still uses the
VS Code-fork layout under ``~/Library/Application Support``:

- ``Devin`` — current product (post-migration)
- ``Windsurf`` / ``Windsurf - Next`` — legacy dirs kept for historical logs

Parsing/attribution lives in ``collectors.vscode_fork``; this module supplies
base dirs, noise markers, and the display source name **Devin Desktop**.
Cascade/Devin agent stores under ``~/.codeium`` are heartbeat-heavy and never
user project work.
"""

from __future__ import annotations

from pathlib import Path

from collectors.vscode_fork import collect_fork_logs, make_noise_filter

# Display name in reports / doctor / collector_status (replaces "Windsurf").
SOURCE_NAME = "Devin Desktop"

# Prefer the current app dir first; keep legacy Windsurf paths for older logs.
DEVIN_APP_DIRS = ("Devin", "Windsurf", "Windsurf - Next")

_WINDSURF_NOISE = make_noise_filter(
    # Machine heartbeats, window/repo lifecycle, and connection churn fire on
    # timers or window open whether or not the user is present — counting them
    # fabricates hours, so they are filtered at ALL profiles (incl. lenient).
    base_extra=(
        # Agent Client Protocol / Devin connection heartbeats (very high volume).
        "acp feature flags",
        "connecting to remote acp",
        "[devin-connect]",
        "scheduling reconnection",
        "authenticated bundled agent",
        "getting sessions for",
        "sessions for all scopes",
        "registering provider with host",
        # Feature-flag/update/extension lifecycle churn.
        "unleash repository",
        "update#setstate",
        "update#islatestversion",
        "extensionservice#_doactivateextension",
        "eager extensions activated",
        "wants api proposal",
        "does not exist. likely",
        "[codeium.windsurf]",
        "cannot register",
        "[diffzone]",
        # Window/git/repository plumbing churn (attributes to the right project
        # but a window open or ref/lock touch is not meaningful work evidence).
        "window will load",
        "skipping acquiring lock for",
        "[model][openrepository]",
        "opened repository",
        "bootstrapping repository index",
        # Shell-resolution failures emitted on every window open, plus the
        # captured subprocess stderr dump they spill (incidental file paths).
        "unable to resolve your shell environment",
        "ptyhost was unable to resolve shell",
        "[stderr]",
        "err_internet_disconnected",
    ),
    ultra_strict=(
        # Broad markers kept out of strict so they can't suppress legitimate
        # editor activity that merely mentions these generic words.
        "websocket connected",
        "websocket closed",
        "initialization complete",
        "telemetry",
        "extensionservice#",
        ".codeium",
        "[vscodediagnosticsexecutor] execute:",
        "baselineresolution",
    ),
)


def windsurf_base_dirs(home: Path) -> list[Path]:
    """Return Devin Desktop + legacy Windsurf application-support directories."""
    support = home / "Library" / "Application Support"
    return [support / name for name in DEVIN_APP_DIRS]


def collect_windsurf(
    profiles,
    dt_from,
    dt_to,
    home,
    local_tz,
    classify_project,
    make_event,
    noise_profile: str = "strict",
):
    """Scrape Devin Desktop (+ legacy Windsurf) logs into project-attributed events.

    Only the app-support base dirs are passed as ``internal_paths``; home-level
    stores (~/.codeium, ~/.cache/devin, …) are already excluded by the shared
    collector's home-dotpath rule.
    """
    base_dirs = windsurf_base_dirs(home)
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
        noise_fn=_WINDSURF_NOISE,
        internal_paths=[str(base) for base in base_dirs],
        noise_profile=noise_profile,
    )
