"""Collector registry construction for report orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional

from collectors.github import github_source_enabled
from collectors.toggl import toggl_source_enabled


@dataclass
class CollectorSpec:
    name: str
    collector: Callable
    unit_label: str
    enabled: bool = True
    reason: Optional[str] = None


def build_collector_specs(
    args: Any,
    worklog_paths: Path | list[Path],
    *,
    chrome_history_exists: bool,
    lovable_desktop_history_exists: bool,
    mail_root: Optional[Path],
    mail_msg: str,
    collect_claude_code: Callable,
    collect_claude_desktop: Callable,
    collect_claude_desktop_code: Callable,
    collect_claude_ai_urls: Callable,
    collect_gemini_web_urls: Callable,
    collect_chrome: Callable,
    collect_lovable_desktop: Callable,
    collect_gemini_cli: Callable,
    collect_copilot_cli: Callable,
    collect_cursor: Callable,
    collect_antigravity: Callable,
    collect_windsurf: Callable,
    collect_cursor_checkpoints: Callable,
    collect_codex_ide: Callable,
    collect_apple_mail: Callable,
    collect_worklog: Callable,
    collect_github: Callable,
    collect_toggl: Callable,
    collect_calendar: Callable,
    collect_zed: Callable,
    collect_conductor: Callable,
    calendar_has_selection: bool = False,
) -> List[CollectorSpec]:
    chrome_enabled = getattr(args, "chrome_source", "on") == "on"
    mail_mode = getattr(args, "mail_source", "auto")
    mail_enabled = mail_mode in {"on", "auto"}
    gh_enabled, gh_reason = github_source_enabled(args)
    toggl_enabled, toggl_reason = toggl_source_enabled(args)
    calendar_enabled = getattr(args, "calendar_source", "off") == "on"
    if not calendar_enabled:
        calendar_reason: Optional[str] = "Consent/source setting disabled"
    elif not calendar_has_selection:
        calendar_reason = "No calendars selected (set --calendar-names)"
    else:
        calendar_reason = None

    return [
        CollectorSpec("Claude Code CLI", collect_claude_code, "events"),
        CollectorSpec("Claude Desktop", collect_claude_desktop, "events"),
        CollectorSpec("Claude Desktop (Code)", collect_claude_desktop_code, "events"),
        CollectorSpec("Claude.ai (specific URLs)", collect_claude_ai_urls, "visits"),
        CollectorSpec("Gemini (web, specific URLs)", collect_gemini_web_urls, "visits"),
        CollectorSpec(
            "Chrome",
            lambda profiles, start, end: collect_chrome(
                profiles, start, end, collapse_minutes=args.chrome_collapse_minutes
            ),
            "visits",
            enabled=chrome_enabled,
            reason="Consent/source setting disabled"
            if not chrome_enabled
            else (None if chrome_history_exists else "Chrome history database not found"),
        ),
        CollectorSpec(
            "Lovable (desktop)",
            collect_lovable_desktop,
            "visits",
            enabled=chrome_enabled,
            reason="Consent/source setting disabled"
            if not chrome_enabled
            else (
                None
                if lovable_desktop_history_exists
                else "Lovable Desktop history database not found"
            ),
        ),
        CollectorSpec("Gemini CLI", collect_gemini_cli, "events"),
        CollectorSpec("GitHub Copilot CLI", collect_copilot_cli, "events"),
        CollectorSpec("Cursor", collect_cursor, "events"),
        CollectorSpec("Cursor checkpoints", collect_cursor_checkpoints, "events"),
        CollectorSpec("Antigravity", collect_antigravity, "events"),
        CollectorSpec("Windsurf", collect_windsurf, "events"),
        CollectorSpec("Codex IDE (OpenAI ~/.codex)", collect_codex_ide, "sessions"),
        CollectorSpec(
            "Apple Mail",
            lambda profiles, start, end: collect_apple_mail(
                profiles, start, end, default_email=args.email
            ),
            "mail",
            enabled=mail_enabled,
            reason="Consent/source setting disabled"
            if not mail_enabled
            else (None if mail_root is not None else mail_msg),
        ),
        CollectorSpec(
            "TIMELOG.md",
            lambda profiles, start, end: collect_worklog(worklog_paths, start, end, profiles),
            "timestamps",
        ),
        CollectorSpec(
            "GitHub",
            collect_github,
            "events",
            enabled=gh_enabled,
            reason=gh_reason,
        ),
        CollectorSpec(
            "Toggl",
            collect_toggl,
            "events",
            enabled=toggl_enabled,
            reason=toggl_reason,
        ),
        CollectorSpec(
            "Calendar",
            collect_calendar,
            "events",
            enabled=calendar_enabled and calendar_has_selection,
            reason=calendar_reason,
        ),
        CollectorSpec("Zed", collect_zed, "events"),
        CollectorSpec("Conductor", collect_conductor, "events"),
    ]
