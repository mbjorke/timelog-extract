"""Interactive mapping assistant — git-local repo bindings, one approval gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.anchor_nudge import should_prompt
from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    load_projects_config_payload,
    remove_rule_from_project,
    save_projects_config_payload,
)
from core.mapping_suggestions import discover_unmapped_git_signals


def collect_actionable_mapping_signals(report, *, include_workspace_repos: bool = False) -> list[dict[str, Any]]:
    """Git repo activity signals for mapping review (no host/title prompts)."""
    profiles = list(getattr(report, "profiles", []) or [])
    events = list(getattr(report, "all_events", None) or getattr(report, "included_events", []) or [])
    if not include_workspace_repos:
        return []

    dt_from = getattr(report, "dt_from", None)
    dt_to = getattr(report, "dt_to", None)
    return discover_unmapped_git_signals(
        profiles,
        events=events,
        dt_from=dt_from,
        dt_to=dt_to,
        local_tz=getattr(dt_from, "tzinfo", None) if dt_from else None,
    )[:10]


def collect_actionable_mapping_signals_from_report(report) -> list[dict[str, Any]]:
    return collect_actionable_mapping_signals(report, include_workspace_repos=False)


def run_setup_evidence_mapping(console, *, config_path: Path, dry_run: bool) -> int:
    """Setup/map sub-step: git repo bindings for configured projects."""
    from core.cli_report_status_helpers import build_report_options, resolve_timeframe_args
    from core.report_service import run_timelog_report

    config = str(config_path.expanduser())
    timeframe = resolve_timeframe_args(
        date_from=None,
        date_to=None,
        today=False,
        yesterday=False,
        last_3_days=False,
        last_week=True,
        last_14_days=False,
        last_month=False,
    )
    options = build_report_options(
        timeframe=timeframe,
        option_fields={
            "projects_config": config,
            "quiet": True,
            "map_prompt": False,
            "screen_time": "off",
        },
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
    events = list(getattr(report, "all_events", None) or getattr(report, "included_events", []) or [])
    signals = collect_actionable_mapping_signals(report, include_workspace_repos=True)
    from core.mapping_review import build_mapping_review, print_mapping_review

    review = build_mapping_review(
        events,
        report.profiles,
        extra_signals=signals,
        dt_from=getattr(report, "dt_from", None),
        dt_to=getattr(report, "dt_to", None),
    )
    if review.change_count() == 0:
        console.print("[dim]No suggested project mapping changes in the last 7 days.[/dim]")
        return 0

    import questionary

    if dry_run:
        console.print("")
        print_mapping_review(console, review)
        console.print(f"[yellow]Dry run:[/yellow] would offer to review {review.change_count()} change(s).")
        return 0

    choice = questionary.select(
        "Map evidence signals to projects?",
        choices=["Map now", "Skip evidence scan", "Cancel setup"],
        default="Map now",
    ).ask()
    if choice == "Cancel setup":
        raise KeyboardInterrupt("setup cancelled by user")
    if choice != "Map now":
        console.print("[dim]Skipped evidence mapping.[/dim]")
        return 0

    applied = run_interactive_mapping_flow(
        console,
        signals,
        report.profiles,
        config,
        events=events,
        dt_from=getattr(report, "dt_from", None),
        dt_to=getattr(report, "dt_to", None),
    )
    if applied:
        console.print("[dim]Evidence rules saved — customer mapping continues below.[/dim]")
    return applied


def reload_projects_after_evidence_mapping(console, *, config_path: Path, dry_run: bool) -> list[dict[str, Any]]:
    run_setup_evidence_mapping(console, config_path=config_path, dry_run=dry_run)
    payload = load_projects_config_payload(config_path)
    return [p for p in payload.get("projects", []) if isinstance(p, dict)]


def _unpack_mapping_addition(
    item: tuple[str, ...],
) -> tuple[str, str, str, str | None, str | None]:
    if len(item) >= 5:
        project_name, rule_type, rule_value, customer, invoice_title = item[:5]
        return project_name, rule_type, rule_value, customer, invoice_title
    if len(item) == 4:
        project_name, rule_type, rule_value, customer = item
        return project_name, rule_type, rule_value, customer, None
    project_name, rule_type, rule_value = item
    return project_name, rule_type, rule_value, None, None


def apply_mapping_additions(
    console,
    additions: list[tuple[str, ...]],
    projects_config: str,
) -> int:
    return apply_mapping_changes(console, additions, [], projects_config)


def apply_mapping_changes(
    console,
    additions: list[tuple[str, ...]],
    removals: list[tuple[str, str, str]],
    projects_config: str,
) -> int:
    """Apply additions and optional removals; return count of changes applied."""
    if not additions and not removals:
        return 0
    cfg_path = Path(projects_config).expanduser()
    payload = load_projects_config_payload(cfg_path)
    removed = 0
    for project_name, rule_type, rule_value in removals:
        if remove_rule_from_project(
            payload,
            project_name=project_name,
            rule_type=rule_type,
            rule_value=rule_value,
        ):
            removed += 1
    for item in additions:
        project_name, rule_type, rule_value, customer, invoice_title = _unpack_mapping_addition(item)
        apply_rule_to_project(
            payload,
            project_name=project_name,
            rule_type=rule_type,
            rule_value=rule_value,
            customer=customer,
            invoice_title=invoice_title,
        )
    backup = backup_projects_config_if_exists(cfg_path)
    if backup:
        console.print(f"[dim]Backup:[/dim] {backup}")
    save_projects_config_payload(cfg_path, payload)
    if additions:
        summary = ", ".join(
            f"{value}→{name}"
            for name, _rtype, value, _customer, _title in (_unpack_mapping_addition(item) for item in additions)
        )
        console.print(f"[green]Mapped {len(additions)} signal(s): {summary}[/green]")
    if removed:
        console.print(
            f"[green]Removed {removed} duplicate github slug(s) from sibling profiles "
            "(profile rows kept).[/green]"
        )
    return len(additions) + removed


def run_interactive_mapping_flow(
    console,
    signals: list[dict[str, Any]],
    profiles: list[dict],
    projects_config: str,
    *,
    events: list[dict[str, Any]] | None = None,
    dt_from: Any = None,
    dt_to: Any = None,
    review: Any | None = None,
) -> int:
    from core.mapping_review import build_mapping_review, run_batch_mapping_review

    if review is None:
        event_list = list(events or [])
        review = build_mapping_review(
            event_list,
            profiles,
            extra_signals=signals,
            dt_from=dt_from,
            dt_to=dt_to,
            local_tz=getattr(dt_from, "tzinfo", None) if dt_from else None,
        )
    if review.change_count() == 0:
        return 0
    batch_result = run_batch_mapping_review(console, review, profiles, projects_config)
    if batch_result is None:
        return 0
    return batch_result


def prepare_mapping_review_after_report(report, *, fast_post_report: bool = False):
    """Build mapping review for the post-report gate; no prompts or console output."""
    from core.mapping_review import build_mapping_review

    events = list(getattr(report, "all_events", None) or getattr(report, "included_events", []) or [])
    dt_from = getattr(report, "dt_from", None)
    dt_to = getattr(report, "dt_to", None)
    local_tz = getattr(dt_from, "tzinfo", None) if dt_from else None

    if fast_post_report:
        return build_mapping_review(
            events,
            report.profiles,
            dt_from=dt_from,
            dt_to=dt_to,
            local_tz=local_tz,
            slug_bindings={},
            gh_discovery=False,
        )

    signals = collect_actionable_mapping_signals(report, include_workspace_repos=True)
    return build_mapping_review(
        events,
        report.profiles,
        extra_signals=signals,
        dt_from=dt_from,
        dt_to=dt_to,
        local_tz=local_tz,
    )


def maybe_run_mapping_assistant_after_report(
    console,
    report,
    *,
    fast_post_report: bool = False,
    review=None,
) -> bool:
    """One gate question on a TTY; then git-local mapping review."""
    if not should_prompt():
        return False
    if getattr(report.args, "map_prompt", True) is False:
        return False
    if str(getattr(report.args, "output_format", "terminal") or "terminal") != "terminal":
        return False

    events = list(getattr(report, "all_events", None) or getattr(report, "included_events", []) or [])
    if review is None:
        review = prepare_mapping_review_after_report(report, fast_post_report=fast_post_report)
    if review.change_count() == 0:
        return False

    import questionary

    console.print()
    console.print(
        f"[bold]Gittan[/bold] found [bold]{review.change_count()}[/bold] possible project mapping "
        f"change{'s' if review.change_count() != 1 else ''}."
    )

    if not questionary.confirm("Review suggested project mapping changes?", default=True).ask():
        console.print("[dim]Skipped — run `gittan map` anytime to review again.[/dim]")
        return False

    config = str(getattr(report, "config_path", None) or getattr(report.args, "projects_config", ""))
    signals: list[dict[str, Any]] = []
    if not fast_post_report:
        signals = collect_actionable_mapping_signals(report, include_workspace_repos=True)
    run_interactive_mapping_flow(
        console,
        signals,
        report.profiles,
        config,
        events=events,
        dt_from=getattr(report, "dt_from", None),
        dt_to=getattr(report, "dt_to", None),
        review=review,
    )
    console.print("[dim]Re-run the same report to see updated project hours.[/dim]")
    return True
