from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from core.repo_slug import resolve_path_repo_slug


def _cwd_leaf(obj) -> str | None:
    """Privacy-safe working-directory leaf (basename) from a Claude Code entry.

    Returns the last path segment (e.g. "timelog-extract") so no home prefix or
    username segment is retained. Absent/blank cwd yields None.
    """
    cwd = obj.get("cwd") if isinstance(obj, dict) else None
    if not cwd:
        return None
    leaf = os.path.basename(str(cwd).rstrip("/\\")).strip().lower()
    return leaf or None


def _meaningful_leaf(name) -> str | None:
    """Directory leaf that is useful as a match_term suggestion, else None.

    Rejects hash-like names (some tools, e.g. Gemini CLI, name their per-project
    tmp directory after a hash of the project path); such a value is noise as a
    suggested match_term, not a human-meaningful project identifier.
    """
    leaf = str(name or "").strip().lower()
    if not leaf:
        return None
    compact = leaf.replace("-", "").replace("_", "")
    if len(compact) >= 16 and all(c in "0123456789abcdef" for c in compact):
        return None
    return leaf


# Branch names that identify a workflow, not a project, are useless as anchors.
_GENERIC_BRANCHES = {"main", "master", "develop", "dev", "trunk", "release", "staging", "prod"}


def _branch_leaf(obj) -> str | None:
    """Privacy-safe project anchor from a git branch name, or None.

    Drops any leading namespace segment (``claude/``, ``feature/``, initials)
    by keeping the part after the last ``/``, and rejects generic workflow
    branches that do not name a project (``main``, ``develop``, …).
    """
    branch = obj.get("gitBranch") if isinstance(obj, dict) else None
    leaf = str(branch or "").strip().rsplit("/", 1)[-1].strip().lower()
    if not leaf or leaf in _GENERIC_BRANCHES:
        return None
    return leaf


# Auto-generated/placeholder session titles carry no project signal.
_GENERIC_LABELS = {"session", "untitled", "new session", "new chat", "conversation"}


def _meaningful_label(name) -> str | None:
    """Session title usable as an anchor, or None for generic placeholders."""
    label = str(name or "").strip().lower()
    if not label or label in _GENERIC_LABELS:
        return None
    return label[:80]


def _anchors(**kinds) -> dict:
    """Collect non-empty {kind: value} anchor pairs into a map."""
    return {kind: value for kind, value in kinds.items() if value}


_CLAUDE_JSONL_SKIP_TYPES = frozenset(
    {
        "pr-link",
        "queue-operation",
        "file-history-snapshot",
        "summary",
        "progress",
    }
)


def _claude_jsonl_is_noise(obj: dict, detail: str) -> bool:
    """Drop system/jsonl rows that are not user-visible Claude work."""
    typ = str(obj.get("type") or "").strip().lower()
    if typ in _CLAUDE_JSONL_SKIP_TYPES:
        return True
    stripped = str(detail or "").strip().lower()
    if stripped in {"", "log"}:
        return True
    if stripped == typ:
        return True
    return False


def _cli_session_id_from_jsonl(jsonl_file: Path) -> str:
    """Map a Claude Code jsonl path to the Desktop session id (cliSessionId)."""
    if jsonl_file.parent.name == "subagents":
        return jsonl_file.parent.parent.name
    return jsonl_file.stem


def _load_claude_code_session_index(home: Path) -> dict[str, dict]:
    """Index Desktop claude-code-sessions metadata by cliSessionId."""
    sessions_dir = home / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
    index: dict[str, dict] = {}
    if not sessions_dir.is_dir():
        return index
    for json_file in sessions_dir.glob("**/local_*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        cli_id = str(data.get("cliSessionId") or "").strip()
        if not cli_id:
            continue
        title = str(data.get("title") or "").strip()
        cwd = str(data.get("cwd") or data.get("originCwd") or "").strip()
        slug = resolve_path_repo_slug(cwd) if cwd else ""
        index[cli_id] = {
            "title": title,
            "label": _meaningful_label(title),
            "cwd": cwd,
            "slug": slug,
            "dir": _cwd_leaf({"cwd": cwd}) if cwd else None,
        }
    return index


def _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
    results = []
    try:
        with open(jsonl_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_raw = obj.get("timestamp") or obj.get("ts") or obj.get("created_at") or obj.get("time")
                if ts_raw is None:
                    continue
                try:
                    if isinstance(ts_raw, (int, float)):
                        divisor = 1000 if ts_raw > 1e11 else 1
                        ts = datetime.fromtimestamp(ts_raw / divisor, tz=timezone.utc)
                    else:
                        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                except (ValueError, OSError):
                    continue

                if not (dt_from <= ts <= dt_to):
                    continue

                msg = obj.get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                    detail = str(content)[:70].replace("\n", " ")
                elif isinstance(msg, str):
                    detail = msg[:70]
                else:
                    detail = str(obj.get("type", ""))[:70]

                results.append((ts, detail or "log", obj))
    except (OSError, PermissionError):
        pass
    return results


def collect_claude_code(profiles, dt_from, dt_to, home, classify_project, make_event):
    results = []
    projects_dir = home / ".claude" / "projects"
    if not projects_dir.exists():
        return results
    session_index = _load_claude_code_session_index(home)
    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        dir_name = proj_dir.name.lower()
        for jsonl_file in proj_dir.glob("*.jsonl"):
            cli_id = _cli_session_id_from_jsonl(jsonl_file)
            meta = session_index.get(cli_id) or {}
            label = meta.get("label")
            meta_title = str(meta.get("title") or "")
            meta_slug = str(meta.get("slug") or "")
            meta_dir = meta.get("dir")
            for ts, detail, obj in _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
                if _claude_jsonl_is_noise(obj, detail):
                    continue
                branch = _branch_leaf(obj)
                cwd = str(obj.get("cwd") or meta.get("cwd") or "") if isinstance(obj, dict) else ""
                # Worktree-invariant attribution: the remote slug is identical
                # across worktrees, so a session in a sibling worktree still
                # classifies to the project even when the path/leaf does not.
                slug = resolve_path_repo_slug(cwd) if cwd else meta_slug
                dir_leaf = _cwd_leaf(obj) if isinstance(obj, dict) else None
                if not dir_leaf:
                    dir_leaf = meta_dir
                project = classify_project(
                    f"{slug} {dir_name} {meta_title} {branch or ''} {detail}", profiles
                )
                results.append(
                    make_event(
                        "Claude Code CLI", ts, detail, project,
                        anchors=_anchors(
                            repo=slug or meta_slug or None,
                            dir=dir_leaf,
                            branch=branch,
                            label=label,
                        ),
                    )
                )
    return results


def collect_claude_desktop(profiles, dt_from, dt_to, home, classify_project, make_event):
    results = []
    sessions_dir = home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    if sessions_dir.exists():
        for jsonl_file in sessions_dir.glob("**/*.jsonl"):
            for ts, detail, obj in _read_jsonl_timestamps(jsonl_file, dt_from, dt_to):
                if _claude_jsonl_is_noise(obj, detail):
                    continue
                project = classify_project(detail, profiles)
                results.append(make_event("Claude Desktop", ts, detail, project))
    return results


def collect_gemini_cli(profiles, dt_from, dt_to, home, classify_project, make_event):
    results = []
    base_dir = home / ".gemini" / "tmp"
    if not base_dir.exists():
        return results
    for chat_file in base_dir.glob("*/chats/session-*.json"):
        proj_name = chat_file.parent.parent.name.lower()
        try:
            data = json.loads(chat_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for msg in data.get("messages", []):
            ts_raw = msg.get("timestamp")
            if not ts_raw:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if not (dt_from <= ts <= dt_to):
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            detail = str(content)[:70].replace("\n", " ")
            role = msg.get("type", "")
            project = classify_project(f"{proj_name} {detail}", profiles)
            results.append(
                make_event(
                    "Gemini CLI",
                    ts,
                    f"[{role}] {detail}" if detail else "Gemini CLI",
                    project,
                    anchors=_anchors(dir=_meaningful_leaf(proj_name)),
                )
            )
    return results


def collect_codex_ide(
    profiles,
    dt_from,
    dt_to,
    codex_session_index: Path,
    classify_project,
    make_event,
):
    if not codex_session_index.is_file():
        return []
    results = []
    try:
        text = codex_session_index.read_text(encoding="utf-8")
    except OSError:
        return []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts_raw = obj.get("updated_at")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if not (dt_from <= ts <= dt_to):
            continue
        thread = str(obj.get("thread_name") or "").strip() or "session"
        sid = str(obj.get("id") or "").replace("-", "")[:10]
        detail = f"{thread[:65]} — id {sid}…" if sid else thread[:70]
        project = classify_project(thread, profiles)
        results.append(
            make_event(
                "Codex IDE", ts, detail, project,
                anchors=_anchors(label=_meaningful_label(thread)),
            )
        )
    return results
