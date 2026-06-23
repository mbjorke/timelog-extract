"""Post-report terminal follow-ups: soft nudges and optional mapping prompt."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from core.anchor_nudge import should_prompt
from core.mapping_assistant import (
    maybe_run_mapping_assistant_after_report,
    prepare_mapping_review_after_report,
)
from core.report_nudges import build_unanchored_anchors_nudge, build_unexplained_gap_nudge
from core.report_service import ReportPayload
from rich.console import Console


def _wants_status(report: ReportPayload) -> bool:
    if getattr(report.args, "quiet", False):
        return False
    if str(getattr(report.args, "output_format", "terminal") or "terminal") != "terminal":
        return False
    return should_prompt()


def _wants_mapping_prompt(report: ReportPayload) -> bool:
    if getattr(report.args, "map_prompt", True) is False:
        return False
    return _wants_status(report)


@contextmanager
def _status(console: Console, report: ReportPayload, message: str) -> Iterator[None]:
    if _wants_status(report):
        with console.status(message, spinner="dots"):
            yield
    else:
        yield


def run_post_report_followups(console: Console, report: ReportPayload) -> None:
    """Print nudges and optional mapping review after the main report table."""
    gap_nudge = build_unexplained_gap_nudge(report)
    if gap_nudge:
        print(gap_nudge)

    mapped_interactively = False
    if _wants_mapping_prompt(report):
        review = None
        with _status(
            console,
            report,
            "[bold blue]Reviewing git bindings for mapping suggestions…[/]",
        ):
            review = prepare_mapping_review_after_report(report, fast_post_report=True)
        mapped_interactively = maybe_run_mapping_assistant_after_report(
            console,
            report,
            fast_post_report=True,
            review=review,
        )

    if not mapped_interactively:
        anchors_nudge = None
        with _status(
            console,
            report,
            "[bold blue]Checking unmapped activity anchors (working dirs, branches, titles)…[/]",
        ):
            anchors_nudge = build_unanchored_anchors_nudge(report)
        if anchors_nudge:
            print(anchors_nudge)


def status_anchor_warn_line(report: ReportPayload, *, console: Console) -> str | None:
    """Return status one-liner for unmapped anchors; show spinner on interactive TTY."""
    from core.anchor_nudge import status_anchor_line
    from core.report_nudges import unanchored_anchors_for_report

    unmapped_anchors = None
    with _status(
        console,
        report,
        "[bold blue]Checking unmapped activity anchors…[/]",
    ):
        unmapped_anchors = unanchored_anchors_for_report(report)
    return status_anchor_line(unmapped_anchors)
