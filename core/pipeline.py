"""Pipeline helpers for collecting events from all enabled sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

def collect_all_events(
    profiles,
    dt_from,
    dt_to,
    args: Any,
    worklog_path: Path,
    *,
    home: Path,
    chrome_history_path_fn: Callable,
    detect_mail_root_fn: Callable,
    build_collector_specs_fn: Callable,
    collect_claude_code: Callable,
    collect_claude_desktop: Callable,
    collect_claude_ai_urls: Callable,
    collect_gemini_web_urls: Callable,
    collect_chrome: Callable,
    collect_gemini_cli: Callable,
    collect_cursor: Callable,
    collect_cursor_checkpoints: Callable,
    collect_codex_ide: Callable,
    collect_apple_mail: Callable,
    collect_worklog: Callable,
    collect_github: Callable,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    all_events: List[Dict[str, Any]] = []
    collector_status: Dict[str, Dict[str, Any]] = {}
    chrome_history_exists = chrome_history_path_fn(home).exists()
    mail_root, mail_msg = detect_mail_root_fn(home)
    collectors = build_collector_specs_fn(
        args,
        worklog_path,
        chrome_history_exists=chrome_history_exists,
        mail_root=mail_root,
        mail_msg=mail_msg,
        collect_claude_code=collect_claude_code,
        collect_claude_desktop=collect_claude_desktop,
        collect_claude_ai_urls=collect_claude_ai_urls,
        collect_gemini_web_urls=collect_gemini_web_urls,
        collect_chrome=collect_chrome,
        collect_gemini_cli=collect_gemini_cli,
        collect_cursor=collect_cursor,
        collect_cursor_checkpoints=collect_cursor_checkpoints,
        collect_codex_ide=collect_codex_ide,
        collect_apple_mail=collect_apple_mail,
        collect_worklog=collect_worklog,
        collect_github=collect_github,
    )
    total_collectors = len(collectors)
    quiet = getattr(args, "quiet", False)

    if quiet:
        for spec in collectors:
            name = spec.name
            if not spec.enabled:
                collector_status[name] = {
                    "enabled": False,
                    "reason": spec.reason,
                    "events": 0,
                }
                continue
            try:
                events = spec.collector(profiles, dt_from, dt_to)
                all_events.extend(events)
                collector_status[name] = {
                    "enabled": True,
                    "reason": spec.reason or "",
                    "events": len(events),
                }
            except Exception as exc:
                collector_status[name] = {
                    "enabled": False,
                    "reason": f"collector error: {exc}",
                    "events": 0,
                }
        return all_events, collector_status

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Scanning sources...", total=total_collectors)
        for spec in collectors:
            name = spec.name
            collector = spec.collector
            unit_label = spec.unit_label
            enabled = spec.enabled
            reason = spec.reason
            
            progress.update(task, description=f"[cyan]Scanning {name}...")
            
            if not enabled:
                collector_status[name] = {
                    "enabled": False,
                    "reason": reason,
                    "events": 0,
                }
                progress.advance(task)
                continue
            
            try:
                events = collector(profiles, dt_from, dt_to)
                all_events.extend(events)
                collector_status[name] = {
                    "enabled": True,
                    "reason": reason or "",
                    "events": len(events),
                }
            except Exception as exc:
                collector_status[name] = {
                    "enabled": False,
                    "reason": f"collector error: {exc}",
                    "events": 0,
                }
            
            progress.advance(task)
            
    return all_events, collector_status
