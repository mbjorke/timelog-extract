from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from collectors.cursor_composer import collect_cursor_composer_sessions
from core.triage_noise import is_uncategorized_noise_detail
from urllib.parse import unquote, urlparse


# Frequent Cursor diagnostics that are operational noise, not user work intent.
# Machine heartbeats/pollers fire on timers for every open workspace whether or
# not the user is present — counting them fabricates hours, so they are filtered
# at ALL profiles (including lenient).
_BASE_NOISE_MARKERS = (
        "error getting submodules",
        "[error] enoent",
        "[error] enotempty",
        "file not found - git:/",
        "[git][revparse] unable to read file: enoent",
        # Periodic git poller (every ~3 min per open workspace, even when idle).
        "git_status: true",
        "git_status: false",
        "> git --git-dir ",
        "candidate index",
        "exthostsearch [cursorignore] internal filesearch start",
        # IDE startup / repo churn — not user intent.
        "cursor_agent_exec.startup.workspace_paths",
        "[model][openrepository] opened repository",
        "bootstrapping repository index at",
        "skipping acquiring lock for",
        "[vscodediagnosticsexecutor] execute:",
        "project config path",
        "claude project config path",
        "claude project local config path",
        "pygls.protocol",
        "glassdiffservice",
        "discover tests for workspace",
        "revived process, old id",
        "failed to handle request",
        '"key":"agent_exec"',
        "send text to terminal: source",
        "active interpreter [global]",
        "error executing git:",
        "difftabcontent",
        "notgitrepository",
        "[worktreemanager]",
        "using worktrees root",
        # Extension-host script runner (statusline/hook polling, fires many
        # times per minute in ~/.claude and similar tool dirs).
        "running script in directory:",
        # Extension marketplace cache refresh — pure IDE plumbing.
        "loadfrommarketplacesource",
        # Config-path polling ("User config path:", "Claude user config path:").
        "user config path:",
        # Extension lifecycle (installs, updates, removal) and helper scripts.
        "installing extension",
        "extension is already requested to install",
        "started downloading extension",
        "extracted extension to",
        "extension installed successfully",
        "uninstalling extension",
        "deleted marked for removal extension",
        ".cursor/extensions",
        "using tsserver from",
        "using askpass script",
        "canvas sdk mirror",
    )
_STRICT_NOISE_MARKERS = (
    # Reserved: ambiguous signals to drop under strict but keep under lenient.
)
_ULTRA_STRICT_NOISE_MARKERS = (
    # Reserved for future extra-aggressive filtering beyond strict.
)


def _compile_noise_markers(*groups: tuple[str, ...]):
    """Single compiled alternation so noise filtering is one regex search per line.

    Equivalent to ``any(marker in text)`` but avoids rebuilding a ~50-item list
    and scanning it per line across millions of Cursor log lines.
    """
    markers = [marker for group in groups for marker in group]
    if not markers:
        return None
    return re.compile("|".join(re.escape(marker) for marker in markers))


_NOISE_MARKER_RE = {
    "lenient": _compile_noise_markers(_BASE_NOISE_MARKERS),
    "strict": _compile_noise_markers(_BASE_NOISE_MARKERS, _STRICT_NOISE_MARKERS),
    "ultra-strict": _compile_noise_markers(
        _BASE_NOISE_MARKERS, _STRICT_NOISE_MARKERS, _ULTRA_STRICT_NOISE_MARKERS
    ),
}


def _is_cursor_diagnostic_noise(line: str, noise_profile: str = "strict") -> bool:
    text = (line or "").lower()
    profile = (noise_profile or "strict").strip().lower()
    marker_re = _NOISE_MARKER_RE.get(profile, _NOISE_MARKER_RE["strict"])
    if marker_re is not None and marker_re.search(text):
        return True
    # skills-cursor sync manifest, file-watcher drops, etc. — shared with review clustering.
    if is_uncategorized_noise_detail(line):
        return True
    # Local Gittan sync/diagnostic artifacts should not count as user work.
    if ".gittan" in text and ("timelog_projects.json" in text or "decisions-" in text):
        if any(marker in text for marker in ("upload", "sync", "error", "enoent", "failed")):
            return True
    return False


def load_cursor_workspaces(home: Path):
    storage_dir = home / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    workspace_map = {}
    if not storage_dir.exists():
        return workspace_map
    for workspace_json in storage_dir.glob("*/workspace.json"):
        workspace_id = workspace_json.parent.name
        try:
            data = json.loads(workspace_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_uri = data.get("folder") or data.get("workspace")
        if not raw_uri:
            continue
        parsed = urlparse(raw_uri)
        path = unquote(parsed.path) if parsed.scheme == "file" else raw_uri
        workspace_map[workspace_id] = path
    return workspace_map


def collect_cursor(profiles, dt_from, dt_to, home, local_tz, classify_project, make_event, noise_profile: str = "strict"):
    workspace_map = load_cursor_workspaces(home)
    logs_dir = home / "Library" / "Application Support" / "Cursor" / "logs"
    if not logs_dir.exists():
        return []

    results = []
    ts_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    ts_iso_bracket_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})?\]")
    workspace_id_pattern = re.compile(r"workspaceStorage/([0-9a-f]{32})|old id ([0-9a-f]{32})-")
    workspace_path_pattern = re.compile(r"(/Users/[^\"'\s]+)")

    def _parse_cursor_log_ts(line: str):
        m = ts_pattern.match(line)
        if m:
            try:
                # fromisoformat accepts "YYYY-MM-DD HH:MM:SS" and is ~20x faster
                # than strptime across millions of log lines (identical result).
                return datetime.fromisoformat(m.group(1)).replace(tzinfo=local_tz)
            except ValueError:
                return None
        m = ts_iso_bracket_pattern.match(line)
        if m:
            iso = (m.group(1) + (m.group(2) or "")).replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(iso)
            except ValueError:
                return None
            # A bracket timestamp without Z/offset parses naive; default it to
            # local_tz so the tz-aware dt_from/dt_to window check never raises.
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=local_tz)
            return parsed
        return None

    # A log file last written before the window starts cannot contain in-window
    # lines (logs are append-only), so skip it without reading — avoids scanning
    # months of rotated Cursor logs on every report.
    from_ts = dt_from.timestamp()
    for log_file in logs_dir.glob("**/*.log"):
        try:
            if log_file.stat().st_mtime < from_ts:
                continue
        except OSError:
            continue
        try:
            with open(log_file, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    ts = _parse_cursor_log_ts(line)
                    if not ts or not (dt_from <= ts <= dt_to):
                        continue
                    if _is_cursor_diagnostic_noise(line, noise_profile=noise_profile):
                        continue
                    workspace_path = None
                    m_id = workspace_id_pattern.search(line)
                    if m_id and workspace_map:
                        workspace_id = m_id.group(1) or m_id.group(2)
                        workspace_path = workspace_map.get(workspace_id)
                    if not workspace_path:
                        m_path = workspace_path_pattern.search(line)
                        if m_path:
                            workspace_path = m_path.group(1)
                    if not workspace_path:
                        continue
                    project = classify_project(f"{workspace_path} {line}", profiles)
                    leaf = Path(workspace_path).name
                    detail = f"{leaf} — {line.strip()[:90]}"
                    dir_leaf = leaf.strip().lower()
                    results.append(
                        make_event(
                            "Cursor", ts, detail, project,
                            anchors={"dir": dir_leaf} if dir_leaf else None,
                        )
                    )
        except OSError:
            continue
    results.extend(
        collect_cursor_composer_sessions(
            profiles, dt_from, dt_to, home, classify_project, make_event
        )
    )
    return results


def collect_cursor_checkpoints(
    profiles,
    dt_from,
    dt_to,
    checkpoints_dir: Path,
    home: Path,
    classify_project,
    make_event,
    source_name: str,
):
    if not checkpoints_dir.is_dir():
        return []
    workspace_map = load_cursor_workspaces(home)
    results = []
    for meta_path in checkpoints_dir.glob("*/metadata.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ms = data.get("startTrackingDateUnixMilliseconds")
        if ms is None:
            continue
        try:
            ts = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            continue
        if not (dt_from <= ts <= dt_to):
            continue
        paths = []
        for rf in data.get("requestFiles") or []:
            p = rf.get("fsPath")
            if p:
                paths.append(str(p))
        wid = data.get("workspaceId")
        workspace_leaf = None
        if wid:
            mapped = workspace_map.get(wid)
            if mapped:
                paths.append(str(mapped))
                # The workspace root is the project leaf; request-file paths are not.
                workspace_leaf = Path(str(mapped)).name.strip().lower() or None
        hay = " ".join(paths)
        if not hay:
            continue
        project = classify_project(hay, profiles)
        agent_id = str(data.get("agentRequestId", "")).split("-")[0][:8]
        label = Path(paths[0]).name if paths else "checkpoint"
        detail = f"checkpoint {agent_id}… — {label}"
        results.append(
            make_event(
                source_name, ts, detail, project,
                anchors={"dir": workspace_leaf} if workspace_leaf else None,
            )
        )
    return results
