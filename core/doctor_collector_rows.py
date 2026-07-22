"""SOURCE_ORDER-aligned doctor rows for local collector prerequisites."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from rich.table import Table

from collectors.conductor import _find_conductor_db
from collectors.lovable_cache import lovable_cache_status, lovable_desktop_has_cache_signals
from collectors.lovable_desktop import (
    lovable_desktop_has_storage_signals,
    lovable_desktop_history_candidates,
)
from collectors.zed import _find_zed_db
from core.cache_evidence_health import codec_missing_reason
from core.doctor_copilot_cli_row import add_copilot_cli_doctor_row
from core.doctor_table_checks import (
    DoctorCheckStyle,
    doctor_check_db,
    doctor_probe_sqlite,
    sqlite_db_probe_ok,
)
from outputs.terminal_theme import FAIL_ICON, NA_ICON, OK_ICON, WARN_ICON


@dataclass
class DoctorCollectorContext:
    """Inputs for registry-aligned collector doctor rows."""

    table: Table
    home: Path
    check_style: DoctorCheckStyle
    ok_icon: str = OK_ICON
    warn_icon: str = WARN_ICON
    fail_icon: str = FAIL_ICON
    na_icon: str = NA_ICON
    style_muted: str = "dim"


def _row(
    ctx: DoctorCollectorContext,
    label: str,
    icon: str,
    detail: str,
) -> None:
    ctx.table.add_row(label, icon, f"[{ctx.style_muted}]{detail}[/{ctx.style_muted}]")


def _row_readable_file(ctx: DoctorCollectorContext, label: str, path: Path) -> bool:
    if not path.exists():
        _row(ctx, label, ctx.na_icon, "Not installed")
        return False
    if not os.access(path, os.R_OK):
        _row(ctx, label, ctx.warn_icon, "No read access")
        return False
    _row(ctx, label, ctx.ok_icon, "Readable")
    return True


def _row_readable_dir(ctx: DoctorCollectorContext, label: str, path: Path, *, optional: bool = True) -> bool:
    if not path.exists():
        _row(ctx, label, ctx.na_icon if optional else ctx.fail_icon, "Not installed")
        return False
    if not os.access(path, os.R_OK):
        _row(ctx, label, ctx.warn_icon, "No read access")
        return False
    _row(ctx, label, ctx.ok_icon, "Readable")
    return True


def _row_logs_dir(ctx: DoctorCollectorContext, label: str, logs_path: Path) -> None:
    if not logs_path.exists():
        _row(ctx, label, ctx.na_icon, "Not installed")
    elif not os.access(logs_path, os.R_OK):
        _row(ctx, label, ctx.warn_icon, "No read access")
    else:
        _row(ctx, label, ctx.ok_icon, "Logs readable")


def _row_web_url_source(ctx: DoctorCollectorContext, label: str, chrome_ok: bool) -> None:
    if chrome_ok:
        _row(ctx, label, ctx.ok_icon, "Chrome History readable")
    else:
        _row(ctx, label, ctx.na_icon, "Requires Chrome History")


def _add_claude_desktop_row(ctx: DoctorCollectorContext) -> None:
    sessions_dir = (
        ctx.home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    )
    if not sessions_dir.exists():
        _row(ctx, "Claude Desktop", ctx.na_icon, "Not installed")
        return
    try:
        has_sessions = any(sessions_dir.glob("**/*.jsonl"))
    except OSError:
        has_sessions = False
    if has_sessions and os.access(sessions_dir, os.R_OK):
        _row(ctx, "Claude Desktop", ctx.ok_icon, "Readable")
    elif os.access(sessions_dir, os.R_OK):
        _row(ctx, "Claude Desktop", ctx.warn_icon, "Installed; no session logs yet")
    else:
        _row(ctx, "Claude Desktop", ctx.warn_icon, "No read access")


def _add_claude_desktop_code_row(ctx: DoctorCollectorContext, codec_blocked: list[str]) -> None:
    from collectors.claude_desktop_events import claude_events_cache_status

    events_ok, events_reason = claude_events_cache_status(ctx.home)
    if codec_missing_reason(events_reason):
        codec_blocked.append("Claude Desktop (Code)")
    icon = ctx.ok_icon if events_ok else (ctx.fail_icon if codec_missing_reason(events_reason) else ctx.na_icon)
    _row(ctx, "Claude Desktop (Code)", icon, events_reason)


def _add_cursor_agent_row(ctx: DoctorCollectorContext) -> None:
    from collectors.cursor_agent_turns import cursor_structured_logs_dir

    logs_dir = cursor_structured_logs_dir(ctx.home)
    if not logs_dir.exists():
        _row(ctx, "Cursor (agent)", ctx.na_icon, "Not installed")
        return
    try:
        has_logs = any(logs_dir.glob("**/*.log"))
    except OSError:
        has_logs = False
    if has_logs and os.access(logs_dir, os.R_OK):
        _row(ctx, "Cursor (agent)", ctx.ok_icon, "Logs readable")
    elif os.access(logs_dir, os.R_OK):
        _row(ctx, "Cursor (agent)", ctx.warn_icon, "Installed; no structured logs yet")
    else:
        _row(ctx, "Cursor (agent)", ctx.warn_icon, "No read access")


def _add_codex_ide_row(ctx: DoctorCollectorContext) -> None:
    index_path = ctx.home / ".codex" / "session_index.jsonl"
    if not index_path.is_file():
        _row(ctx, "Codex IDE", ctx.na_icon, "Not installed")
        return
    if os.access(index_path, os.R_OK):
        _row(ctx, "Codex IDE", ctx.ok_icon, "Readable")
    else:
        _row(ctx, "Codex IDE", ctx.warn_icon, "No read access")


def _add_gemini_cli_row(ctx: DoctorCollectorContext) -> None:
    base_dir = ctx.home / ".gemini" / "tmp"
    if not base_dir.exists():
        _row(ctx, "Gemini CLI", ctx.na_icon, "Not installed")
        return
    try:
        has_chats = any(base_dir.glob("*/chats/session-*.json"))
    except OSError:
        has_chats = False
    if has_chats and os.access(base_dir, os.R_OK):
        _row(ctx, "Gemini CLI", ctx.ok_icon, "Readable")
    elif os.access(base_dir, os.R_OK):
        _row(ctx, "Gemini CLI", ctx.warn_icon, "Installed; no chat sessions yet")
    else:
        _row(ctx, "Gemini CLI", ctx.warn_icon, "No read access")


def _add_zed_row(ctx: DoctorCollectorContext) -> None:
    db_path = _find_zed_db(ctx.home)
    if db_path is None:
        _row(ctx, "Zed", ctx.na_icon, "Not installed")
        return
    doctor_probe_sqlite(ctx.table, db_path, "Zed", ctx.check_style)


def _add_conductor_row(ctx: DoctorCollectorContext) -> None:
    db_path = _find_conductor_db(ctx.home)
    if db_path is None:
        _row(ctx, "Conductor", ctx.na_icon, "Not installed")
        return
    doctor_probe_sqlite(ctx.table, db_path, "Conductor", ctx.check_style)


def _add_lovable_row(ctx: DoctorCollectorContext, codec_blocked: list[str]) -> None:
    lh = lovable_desktop_history_candidates(ctx.home)
    if lh:
        doctor_check_db(ctx.table, lh[0], "Lovable (desktop)", "urls", ctx.check_style)
        return
    if lovable_desktop_has_storage_signals(ctx.home) or lovable_desktop_has_cache_signals(ctx.home):
        cache_ok, cache_reason = lovable_cache_status(ctx.home)
        if codec_missing_reason(cache_reason):
            codec_blocked.append("Lovable (desktop)")
        icon = (
            ctx.fail_icon
            if codec_missing_reason(cache_reason)
            else (ctx.ok_icon if cache_ok else ctx.na_icon)
        )
        _row(ctx, "Lovable (desktop)", icon, cache_reason)
    else:
        _row(ctx, "Lovable (desktop)", ctx.na_icon, "Not installed")


def _add_calendar_row(ctx: DoctorCollectorContext) -> None:
    from collectors.calendar import detect_calendar_db

    _cal_db, cal_status = detect_calendar_db(ctx.home)
    if _cal_db is not None:
        _row(ctx, "Calendar", ctx.ok_icon, "Readable (opt-in: --calendar-source on)")
    elif cal_status == "Full Disk Access required":
        _row(ctx, "Calendar", ctx.fail_icon, "Full Disk Access required")
    else:
        _row(ctx, "Calendar", ctx.na_icon, cal_status)


def _add_apple_mail_row(ctx: DoctorCollectorContext) -> None:
    mail_path = ctx.home / "Library" / "Mail"
    if not mail_path.exists():
        _row(ctx, "Apple Mail", ctx.na_icon, "Not installed")
        return
    try:
        list(mail_path.glob("V[0-9]*"))
        _row(ctx, "Apple Mail", ctx.ok_icon, "Readable")
    except PermissionError:
        _row(ctx, "Apple Mail", ctx.fail_icon, "Full Disk Access required")


def add_collector_doctor_rows(
    table: Table,
    home: Path,
    check_style: DoctorCheckStyle,
    *,
    codec_blocked: list[str],
    ok_icon: str = OK_ICON,
    warn_icon: str = WARN_ICON,
    fail_icon: str = FAIL_ICON,
    na_icon: str = NA_ICON,
    style_muted: str = "dim",
) -> None:
    """Append collector rows grouped AI/IDE → passive → reference (SOURCE_ORDER)."""
    ctx = DoctorCollectorContext(
        table=table,
        home=home,
        check_style=check_style,
        ok_icon=ok_icon,
        warn_icon=warn_icon,
        fail_icon=fail_icon,
        na_icon=na_icon,
        style_muted=style_muted,
    )

    chrome_path = home / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
    chrome_ok = sqlite_db_probe_ok(chrome_path, table_name="urls")

    # --- AI / IDE (SOURCE_ORDER) ---
    claude_projects = home / ".claude" / "projects"
    if claude_projects.exists() and os.access(claude_projects, os.R_OK):
        _row(ctx, "Claude Code CLI", ctx.ok_icon, "Readable")
    else:
        _row(ctx, "Claude Code CLI", ctx.na_icon, "Not installed")

    _add_claude_desktop_row(ctx)
    _add_claude_desktop_code_row(ctx, codec_blocked)
    _row_web_url_source(ctx, "Claude.ai (web)", chrome_ok)
    _row_web_url_source(ctx, "Gemini (web)", chrome_ok)

    cursor_log_path = (
        home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "storage.json"
    )
    _row_readable_file(ctx, "Cursor", cursor_log_path)

    _add_cursor_agent_row(ctx)

    cursor_checkpoints = (
        home
        / "Library/Application Support/Cursor/User/globalStorage/anysphere.cursor-commits/checkpoints"
    )
    _row_readable_dir(ctx, "Cursor checkpoints", cursor_checkpoints)

    from collectors.antigravity import antigravity_base_dir
    from collectors.vscode import vscode_base_dirs
    from collectors.windsurf import windsurf_base_dirs

    _row_logs_dir(ctx, "Antigravity", antigravity_base_dir(home) / "logs")

    windsurf_logs = [base / "logs" for base in windsurf_base_dirs(home)]
    present = [p for p in windsurf_logs if p.exists()]
    if not present:
        _row(ctx, "Devin Desktop", ctx.na_icon, "Not installed")
    elif not any(os.access(p, os.R_OK) for p in present):
        _row(ctx, "Devin Desktop", ctx.warn_icon, "No read access")
    else:
        _row(ctx, "Devin Desktop", ctx.ok_icon, "Logs readable")

    vscode_logs = [base / "logs" for base in vscode_base_dirs(home)]
    vscode_present = [p for p in vscode_logs if p.exists()]
    if not vscode_present:
        _row(ctx, "VS Code", ctx.na_icon, "Not installed")
    elif not any(os.access(p, os.R_OK) for p in vscode_present):
        _row(ctx, "VS Code", ctx.warn_icon, "No read access")
    else:
        _row(ctx, "VS Code", ctx.ok_icon, "Logs readable")

    _add_codex_ide_row(ctx)

    add_copilot_cli_doctor_row(
        table,
        home,
        ok_icon=ok_icon,
        warn_icon=warn_icon,
        na_icon=na_icon,
        style_muted=style_muted,
    )

    _add_gemini_cli_row(ctx)
    _add_zed_row(ctx)
    _add_conductor_row(ctx)

    # --- Passive context ---
    _add_apple_mail_row(ctx)
    doctor_check_db(table, chrome_path, "Chrome", "urls", check_style)
    _row_web_url_source(ctx, "WordPress", chrome_ok)
    _row_web_url_source(ctx, "Lovable (web)", chrome_ok)
    _add_lovable_row(ctx, codec_blocked)

    # --- Opt-in scheduled ---
    _add_calendar_row(ctx)

    # --- Reference (coverage comparator) ---
    st_path = home / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db"
    if not st_path.exists():
        st_path = home / "Library" / "Application Support" / "KnowledgeC" / "knowledgeC.db"
    doctor_check_db(table, st_path, "Screen Time", "ZOBJECT", check_style)
