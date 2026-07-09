"""Glass/Multitask label enrichment when ``composer.composerHeaders`` is missing.

Multitask chats often appear in hooks logs without a composer header. Glass PR
tabs may still expose a short ``label`` (and rarely ``branchName``) keyed by
``ownerAgentId`` (= conversation_id). For the common case with no PR tab, read
the current git branch under ``workspace_roots``.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from collectors.ai_logs import _GENERIC_BRANCHES
from collectors.cursor_composer import cursor_state_db_path
from core.worklog_enrich import is_pr_number_session_label

_GLASS_TABS_KEY_PREFIX = "cursor/glass.tabs.v2/"


def _branch_name_leaf(branch: str | None) -> str | None:
    """Privacy-safe branch leaf (after last ``/``), rejecting generic workflow names."""
    leaf = str(branch or "").strip().rsplit("/", 1)[-1].strip().lower()
    if not leaf or leaf in _GENERIC_BRANCHES:
        return None
    return leaf


def git_branch_leaf_at_path(repo_path: str) -> str | None:
    """Current HEAD branch leaf under ``workspace_roots``, or None if unavailable.

    ``workspace_roots`` may be a subdirectory inside a git work tree; rely on
    ``git -C`` discovery rather than requiring ``<path>/.git`` to exist.
    """
    path = Path(repo_path)
    if not repo_path or not path.is_dir():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return _branch_name_leaf(result.stdout.strip())


def load_glass_agent_tab_meta(home: Path) -> dict[str, dict[str, str]]:
    """Map Glass tab ``ownerAgentId`` (conversation_id) → label / branch leaf.

    Coverage is partial (PR tabs only). Callers should still fall back to git.
    """
    db_path = cursor_state_db_path(home)
    if not db_path.is_file():
        return {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT key, value FROM ItemTable WHERE key LIKE ?",
            (f"{_GLASS_TABS_KEY_PREFIX}%",),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return {}

    out: dict[str, dict[str, str]] = {}
    for _key, raw in rows:
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for section in ("stableTabs", "workspaceTabs"):
            tabs = payload.get(section)
            if not isinstance(tabs, list):
                continue
            for tab in tabs:
                if not isinstance(tab, dict):
                    continue
                props = tab.get("props")
                if not isinstance(props, dict):
                    continue
                agent_id = str(props.get("ownerAgentId") or "").strip()
                if not agent_id:
                    continue
                label = str(tab.get("label") or "").strip()
                # GH-351: PR-tab titles like ``PR #347: …`` overpaint Multitask
                # sessions; keep branchName / git fallback, drop the label.
                if is_pr_number_session_label(label):
                    label = ""
                branch = _branch_name_leaf(str(props.get("branchName") or ""))
                prev = out.get(agent_id, {})
                merged: dict[str, str] = dict(prev)
                if label and not merged.get("label"):
                    merged["label"] = label
                if branch and not merged.get("branch"):
                    merged["branch"] = branch
                if merged:
                    out[agent_id] = merged
    return out
