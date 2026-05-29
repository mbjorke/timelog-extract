"""Collector for Google Antigravity IDE activity.

Antigravity IDE is a VS Code fork (the agentic IDE from Google), so its
on-disk layout mirrors Cursor: ``~/Library/Application Support/Antigravity IDE``
holds ``User/workspaceStorage/<id>/workspace.json`` folder mappings and a
timestamped ``logs/`` tree. Parsing/attribution lives in
``collectors.vscode_fork``; this module only supplies Antigravity's base dir,
noise markers, and internal data dirs.
"""

from __future__ import annotations

from pathlib import Path

from collectors.vscode_fork import collect_fork_logs, make_noise_filter

# The IDE stores data under "Antigravity IDE"; the sibling "Antigravity"
# directory belongs to the standalone launcher app and has no workspace logs.
ANTIGRAVITY_APP_DIR = "Antigravity IDE"

_ANTIGRAVITY_NOISE = make_noise_filter(
    strict=(
        # Editor/extension lifecycle churn at startup.
        "extensionservice#_doactivateextension",
        "eager extensions activated",
        "wants api proposal",
        "does not exist. likely",
        "update#setstate",
        "running one-time migration",
        "skipping migration",
        # Antigravity language-server (Go) heartbeats and polling.
        "starting language server process",
        "setting gomaxprocs",
        "listening on random port",
        "created extension server client",
        "failed to poll listexperiments",
        "singleflight refresh failed",
    ),
    ultra_strict=(
        # Aggressive filtering for onboarding, telemetry, and artifact churn.
        "browseronboarding",
        "extensionservice#",
        "telemetry",
        ".gemini/antigravity-ide",
        "html_artifacts",
        "[vscodediagnosticsexecutor] execute:",
    ),
)


def antigravity_base_dir(home: Path) -> Path:
    """Return the Antigravity IDE application-support directory for ``home``."""
    return home / "Library" / "Application Support" / ANTIGRAVITY_APP_DIR


def collect_antigravity(
    profiles,
    dt_from,
    dt_to,
    home,
    local_tz,
    classify_project,
    make_event,
    noise_profile: str = "strict",
):
    """Scrape Antigravity IDE logs into project-attributed activity events.

    Only the app-support base dir is passed as ``internal_paths``; Antigravity's
    home-level stores (~/.antigravity-ide, ~/.gemini/antigravity-ide) are
    already excluded by the shared collector's home-dotpath rule.
    """
    base_dir = antigravity_base_dir(home)
    return collect_fork_logs(
        profiles,
        dt_from,
        dt_to,
        home,
        local_tz,
        classify_project,
        make_event,
        source_name="Antigravity",
        base_dirs=[base_dir],
        noise_fn=_ANTIGRAVITY_NOISE,
        internal_paths=[str(base_dir)],
        noise_profile=noise_profile,
    )
