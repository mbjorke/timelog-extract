"""Post-report terminal follow-ups: soft nudges and optional mapping prompt."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.anchor_nudge import should_prompt
from core.mapping_assistant import maybe_run_mapping_assistant_after_report
from core.report_nudges import build_unanchored_anchors_nudge, build_unexplained_gap_nudge
from rich.console import Console

if TYPE_CHECKING:
    from core.report_service import ReportPayload


def _wants_mapping_prompt(report: ReportPayload) -> bool:
    return (
        should_prompt()
        and getattr(report.args, "map_prompt", True) is not False
        and str(getattr(report.args, "output_format", "terminal") or "terminal") == "terminal"
    )


def _show_status_spinner(report: ReportPayload) -> bool:
    if getattr(getattr(report, "args", None), "quiet", False):
        return False
    return should_prompt()


def run_post_report_followups(report: ReportPayload) -> None:
    """Print nudges and optional mapping review after the main report table.

    The main hours table is already on screen; this phase can still scan local git
    clones, Cursor logs, and ``gh repo list`` for mapping review — hence the
    explicit status lines instead of a silent hang.
    """
    gap_nudge = build_unexplained_gap_nudge(report)
    if gap_nudge:
        print(gap_nudge)

    console = Console()
    use_status = _show_status_spinner(report)
    mapped_interactively = False
    if _wants_mapping_prompt(report):
        if use_status:
            with console.status(
                "[bold blue]Checking for suggested project mapping changes…[/]",
                spinner="dots",
            ):
                mapped_interactively = maybe_run_mapping_assistant_after_report(console, report)
        else:
            mapped_interactively = maybe_run_mapping_assistant_after_report(console, report)

    if not mapped_interactively:
        if use_status:
            with console.status(
                "[bold blue]Checking unmapped activity anchors (working dirs, branches, titles)…[/]",
                spinner="dots",
            ):
                anchors_nudge = build_unanchored_anchors_nudge(report)
        else:
            anchors_nudge = build_unanchored_anchors_nudge(report)
        if anchors_nudge:
            print(anchors_nudge)


def print_status_anchor_followup(console, report) -> None:
    """Status command: spinner while scanning anchors, then read-only warning."""
    from core.anchor_nudge import status_anchor_line
    from core.report_nudges import unanchored_anchors_for_report
    from outputs.terminal_theme import CLR_VALUE_ORANGE, STYLE_MUTED

    if should_prompt():
        with console.status(
            "[bold blue]Checking unmapped activity anchors (working dirs, branches, titles)…[/]",
            spinner="dots",
        ):
            unmapped_anchors = unanchored_anchors_for_report(report)
    else:
        unmapped_anchors = unanchored_anchors_for_report(report)
    warn_line = status_anchor_line(unmapped_anchors)
    if not warn_line:
        return
    console.print(f"[{CLR_VALUE_ORANGE}]{warn_line}[/{CLR_VALUE_ORANGE}]")
    console.print(
        f"[{STYLE_MUTED}]Run `gittan map` to review and apply project mappings.[/{STYLE_MUTED}]"
    )
