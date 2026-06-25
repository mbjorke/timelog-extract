"""Post-report terminal follow-ups: soft nudges and optional mapping prompt."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from rich.console import Console

from core.anchor_nudge import should_prompt
from core.mapping_assistant import (
    maybe_run_mapping_assistant_after_report,
    prepare_mapping_review_after_report,
)
from core.report_nudges import (
    build_unanchored_anchors_nudge,
    build_unexplained_gap_nudge,
    unanchored_anchors_for_report,
)
from core.report_service import ReportPayload
from outputs.terminal_theme import CLR_DIM


def _wants_spinner(report: ReportPayload, *, ignore_quiet: bool = False) -> bool:
    """True when Rich status spinners may run (TTY + terminal output)."""
    if not ignore_quiet and getattr(report.args, "quiet", False):
        return False
    if str(getattr(report.args, "output_format", "terminal") or "terminal") != "terminal":
        return False
    return should_prompt()


def _wants_interactive_status(report: ReportPayload, *, ignore_quiet: bool = False) -> bool:
    """True when post-report prompts may run (TTY, terminal format, not quiet)."""
    return _wants_spinner(report, ignore_quiet=ignore_quiet)


def _wants_status(report: ReportPayload) -> bool:
    """True when Rich status spinners may run during post-report follow-ups."""
    return _wants_interactive_status(report)


def _wants_mapping_prompt(report: ReportPayload) -> bool:
    """True when the optional git-mapping question may run after a report."""
    if getattr(report.args, "map_prompt", True) is False:
        return False
    return _wants_status(report)


@contextmanager
def _status(console: Console, report: ReportPayload, message: str) -> Iterator[None]:
    """Show a Rich spinner while post-report work runs on interactive terminals."""
    if _wants_status(report):
        with console.status(message, spinner="dots"):
            yield
    else:
        yield


def run_post_report_followups(console: Console, report: ReportPayload) -> None:
    """Print nudges and optional mapping review after the main report table."""
    gap_nudge = build_unexplained_gap_nudge(report)
    if gap_nudge:
        console.print(gap_nudge)

    mapped_interactively = False
    if _wants_mapping_prompt(report):
        review = None
        with _status(
            console,
            report,
            f"[{CLR_DIM}]Reviewing git bindings for mapping suggestions…[/{CLR_DIM}]",
        ):
            review = prepare_mapping_review_after_report(report, fast_post_report=True)
        mapped_interactively = maybe_run_mapping_assistant_after_report(
            console,
            report,
            fast_post_report=True,
            review=review,
        )

    if not mapped_interactively:
        console.print()
        unmapped_anchors: list[dict] = []
        with _status(
            console,
            report,
            f"[{CLR_DIM}]Checking unmapped activity anchors (working dirs, branches, titles)…[/{CLR_DIM}]",
        ):
            unmapped_anchors = unanchored_anchors_for_report(report)
        anchors_nudge = build_unanchored_anchors_nudge(report, anchors=unmapped_anchors)
        if anchors_nudge:
            console.print(anchors_nudge)


def scan_unmapped_anchors_with_status(
    console: Console,
    report: ReportPayload,
    *,
    message: str = f"[{CLR_DIM}]Checking unmapped activity anchors…[/{CLR_DIM}]",
    ignore_quiet: bool = False,
) -> list[dict]:
    """Scan for unmapped anchors; show a Rich spinner on interactive terminals."""
    if _wants_spinner(report, ignore_quiet=ignore_quiet):
        with console.status(message, spinner="dots"):
            return unanchored_anchors_for_report(report)
    return unanchored_anchors_for_report(report)


def status_anchor_warn_line(
    report: ReportPayload,
    *,
    console: Console,
    ignore_quiet: bool = False,
) -> str | None:
    """Return status one-liner for unmapped anchors; show spinner on interactive TTY."""
    from core.anchor_nudge import status_anchor_line

    unmapped_anchors = scan_unmapped_anchors_with_status(console, report, ignore_quiet=ignore_quiet)
    return status_anchor_line(unmapped_anchors)
