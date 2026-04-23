"""Deterministic stub output for live terminal demo (no real `gittan` execution)."""

from __future__ import annotations

from typing import Final

from core.live_terminal.contract import normalize_demo_command_line
from core.live_terminal.mock_data import load_demo_mock_data

_STUB_HELP: Final[str] = """\
Demo sandbox — allowlisted commands:
  gittan doctor
  gittan report --today --source-summary
  gittan report --today --format json
  gittan report --today --invoice-pdf
  help
  clear
"""


def _doctor_output() -> str:
    fixture = load_demo_mock_data()
    doctor = fixture.get("doctor", {})
    title = str(doctor.get("title", "Gittan Health Check (demo)"))
    rows = doctor.get("rows", [])
    lines = [title]
    for name, status in rows:
        lines.append(f"{name:<20} {status}")
    return "\n".join(lines) + "\n"


def _source_summary_output() -> str:
    fixture = load_demo_mock_data()
    source_summary = fixture.get("source_summary", {})
    rows = source_summary.get("rows", [])
    total = int(source_summary.get("total", 0))
    lines = ["Source summary (demo fixture)"]
    for source, count in rows:
        lines.append(f"{source:<20} {int(count)}")
    lines.append(f"Total: {total}")
    return "\n".join(lines) + "\n"


def _json_output() -> str:
    fixture = load_demo_mock_data()
    payload = fixture.get("truth_payload", {})
    import json

    return json.dumps(payload, ensure_ascii=False) + "\n"


def demo_stub_output(line: str) -> str:
    """Return multiline text for an allowlisted command line (validated by caller)."""
    key = normalize_demo_command_line(line)
    if key == "help":
        return _STUB_HELP
    if key == "clear":
        return "[demo] Screen cleared.\n"
    if key == "gittan doctor":
        return _doctor_output()
    if key == "gittan report --today --source-summary":
        return _source_summary_output()
    if key == "gittan report --today --format json":
        return _json_output()
    if key == "gittan report --today --invoice-pdf":
        return "Invoice PDF (demo stub): not generated in sandbox mode\n"
    raise ValueError(f"Unhandled allowlisted demo command in stub output: {key}")

