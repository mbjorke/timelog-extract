"""Collector for Windsurf IDE activity (Codeium/Cognition).

Windsurf is a VS Code fork sharing the Antigravity/Cursor layout:
``~/Library/Application Support/Windsurf`` (and the beta ``Windsurf - Next``)
hold ``User/workspaceStorage/<id>/workspace.json`` folder mappings and a
timestamped ``logs/`` tree. Parsing/attribution lives in
``collectors.vscode_fork``; this module only supplies Windsurf's base dirs,
noise markers, and internal data dirs (Cascade/Devin agent stores under
``~/.codeium`` are heartbeat-heavy and never user project work).
"""

from __future__ import annotations

from pathlib import Path

from collectors.vscode_fork import collect_fork_logs, make_noise_filter

# Both the stable channel and the "Next" beta share the same layout.
WINDSURF_APP_DIRS = ("Windsurf", "Windsurf - Next")

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
    """Return the Windsurf application-support directories for ``home``."""
    support = home / "Library" / "Application Support"
    return [support / name for name in WINDSURF_APP_DIRS]


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
    """Scrape Windsurf (stable + Next) logs into project-attributed events.

    Only the app-support base dirs are passed as ``internal_paths``; Windsurf's
    home-level stores (~/.codeium, ~/.cache/devin, …) are already excluded by
    the shared collector's home-dotpath rule.
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
        source_name="Windsurf",
        base_dirs=base_dirs,
        noise_fn=_WINDSURF_NOISE,
        internal_paths=[str(base) for base in base_dirs],
        noise_profile=noise_profile,
    )
