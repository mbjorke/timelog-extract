"""Deterministic stub output for live terminal demo (no real `gittan` execution)."""

from __future__ import annotations

from typing import Final

from core.live_terminal.contract import normalize_demo_command_line

_STUB_HELP: Final[str] = """\
Demo sandbox — allowlisted commands:
  gittan doctor
  gittan report --today --source-summary
  gittan report --today --format json
  gittan report --today --invoice-pdf
  help
  clear
"""


def demo_stub_output(line: str) -> str:
    """Return multiline text for an allowlisted command line (validated by caller)."""
    key = normalize_demo_command_line(line)
    if key == "help":
        return _STUB_HELP
    if key == "clear":
        return "[demo] Screen cleared.\n"
    if key == "gittan doctor":
        return (
            "Gittan Health Check (demo stub)\n"
            "Project Config     OK\n"
            "Worklog (Local)    OK\n"
            "GitHub Copilot CLI NA (demo)\n"
        )
    if key == "gittan report --today --source-summary":
        return (
            "Source summary (demo stub)\n"
            "Cursor              0\n"
            "TIMELOG.md          0\n"
            "Total: 0\n"
        )
    if key == "gittan report --today --format json":
        return (
            '{"schema":"timelog_extract.truth_payload","version":1,"demo":true,'
            '"totals":{"event_count":0,"hours_estimated":0}}\n'
        )
    if key == "gittan report --today --invoice-pdf":
        return "Invoice PDF (demo stub): not generated in sandbox mode\n"
    raise ValueError(f"Unhandled allowlisted demo command in stub output: {key}")

