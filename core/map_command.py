"""Orchestration for `gittan map` — anchors first, optional repo scan."""

from __future__ import annotations

import time

from core.anchor_nudge import maybe_run_interactive_anchor_mapping, should_prompt
from core.map_repo_hints import unconfigured_repo_slugs_in_events
from core.mapping_assistant import run_interactive_mapping_flow
from core.mapping_review import build_mapping_review
from outputs.terminal_theme import STYLE_LABEL, STYLE_MUTED


def _repo_scan_prompt(hints: list[str]) -> str:
    preview = ", ".join(hints[:3])
    if len(hints) > 3:
        preview = f"{preview} +{len(hints) - 3} more"
    return f"Scan local git clones and GitHub for repo mappings? ({preview})"


def run_map_command(
    console,
    *,
    options,
    projects_config: str,
    scan_repos: bool,
) -> tuple[bool, bool, list[str]]:
    """Run map flow: report → anchors → optional repo scan.

    Returns ``(anchors_applied, repo_mapping_applied, repo_hints)``.
    """
    from core.report_service import run_timelog_report

    collect_started = time.perf_counter()
    with console.status(f"[{STYLE_LABEL}]Collecting activity signals…[/]"):
        report_started = time.perf_counter()
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
        report_elapsed = time.perf_counter() - report_started
    collect_elapsed = time.perf_counter() - collect_started
    console.print(f"[{STYLE_MUTED}]Activity collected in {collect_elapsed:.1f}s (report {report_elapsed:.1f}s).[/]")

    config = str(getattr(report, "config_path", None) or projects_config)
    events = list(getattr(report, "all_events", None) or getattr(report, "included_events", []) or [])
    hints = unconfigured_repo_slugs_in_events(events, list(report.profiles or []))

    anchors_applied = maybe_run_interactive_anchor_mapping(console, report, projects_config=config)

    run_repo_scan = bool(scan_repos)
    if not run_repo_scan and hints:
        if should_prompt():
            import questionary

            answer = questionary.confirm(_repo_scan_prompt(hints), default=True).ask()
            run_repo_scan = bool(answer)
        else:
            run_repo_scan = True

    if not run_repo_scan:
        return anchors_applied, False, hints

    review_started = time.perf_counter()
    with console.status(f"[{STYLE_LABEL}]Scanning local git clones and GitHub…[/]"):
        review = build_mapping_review(
            events,
            report.profiles,
            dt_from=getattr(report, "dt_from", None),
            dt_to=getattr(report, "dt_to", None),
            local_tz=getattr(report, "dt_from", None).tzinfo if getattr(report, "dt_from", None) else None,
        )
    review_elapsed = time.perf_counter() - review_started
    console.print(f"[{STYLE_MUTED}]Repo scan {review_elapsed:.1f}s.[/]")

    if review.change_count() == 0:
        console.print(f"[{STYLE_MUTED}]No repo mapping changes suggested for this window.[/]")
        return anchors_applied, False, hints

    applied = run_interactive_mapping_flow(
        console,
        [],
        report.profiles,
        config,
        review=review,
    )
    return anchors_applied, bool(applied), hints


def map_exit_message(*, anchors_applied: bool, repo_applied: bool, had_repo_hints: bool) -> str:
    if anchors_applied or repo_applied:
        return "[dim]Re-run `gittan report` for the same window to verify project hours.[/dim]"
    if had_repo_hints:
        return (
            "[dim]Skipped repo scan — run `gittan map --scan-repos` to search local clones and GitHub.[/dim]"
        )
    return (
        "[dim]Nothing to map in this window. "
        "Use `gittan map --scan-repos` to search for new GitHub repos and duplicate variants.[/dim]"
    )
