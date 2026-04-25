"""Deterministic stub output for live terminal demo (no real `gittan` execution)."""

from __future__ import annotations

from typing import Final

from core.live_terminal.contract import normalize_demo_command_line
from core.live_terminal.mock_data import load_demo_mock_data

_STUB_HELP: Final[str] = """\
Demo sandbox — allowlisted commands:
  gittan doctor
  gittan setup --dry-run
  gittan setup
  gittan status
  gittan report
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
    lines = [
        title,
        "Local-first checks for a safe demo path.",
        "",
    ]
    for name, status in rows:
        lines.append(f"{name:<22} {status}")
    lines.extend(
        [
            "",
            "Next: run `gittan report --today --source-summary`",
        ]
    )
    return "\n".join(lines) + "\n"


def _source_summary_output() -> str:
    fixture = load_demo_mock_data()
    source_summary = fixture.get("source_summary", {})
    rows = source_summary.get("rows", [])
    total = int(source_summary.get("total", 0))
    lines = [
        "Gittan report — today (demo fixture)",
        "Source summary",
        "",
    ]
    for source, count in rows:
        lines.append(f"{source:<22} {int(count)} events")
    lines.append(f"Total: {total}")
    lines.extend(
        [
            "",
            "Observed time:             2.1h",
            "Classified candidates:    1.8h",
            "Approved invoice time:    0.0h (human review required)",
            "",
            "Gittan organizes evidence; it does not approve invoice truth.",
            "Optional: run `gittan report --today --format json`",
        ]
    )
    return "\n".join(lines) + "\n"


def _setup_dry_run_output() -> str:
    return """\
Gittan setup — dry run (demo fixture)

Would check:
  ✓ Python package and CLI entrypoint
  ✓ local project config path
  ✓ local worklog path
  ✓ optional GitHub environment
  ✓ global timelog automation prompt

No files were changed.
Next: run `gittan setup` when you are ready.
"""


def _setup_output() -> str:
    return """\
Gittan setup — demo fixture

Environment checks       PASS
Project config           READY — demo projects loaded
Global timelog           SKIPPED — demo mode
Smoke report             PASS — local evidence available

Next: run `gittan doctor`
Then: run `gittan report --today --source-summary`
"""


def _status_output() -> str:
    return """\
Gittan Status — today (demo fixture)
Timeframe prompt: Today selected for demo.

Hours Summary (unique timeline)
Project                Hours   Sessions   State
Gittan                 1.2h    3          work
Client A               0.6h    2          needs review
Ops                    0.3h    1          observed
────────────────────────────────────────────────
Total                  2.1h    6          observed

Observed time:             2.1h
Classified candidates:    1.8h
Approved invoice time:    0.0h (human review required)

Note: project rows are candidate attribution. Invoice approval is still manual.
Next: run `gittan report --today --source-summary`
"""


def _json_output() -> str:
    fixture = load_demo_mock_data()
    payload = fixture.get("truth_payload", {})
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def demo_stub_output(line: str) -> str:
    """Return multiline text for an allowlisted command line (validated by caller)."""
    key = normalize_demo_command_line(line)
    if key == "help":
        return _STUB_HELP
    if key == "clear":
        return "[demo] Screen cleared.\n"
    if key == "gittan doctor":
        return _doctor_output()
    if key == "gittan setup --dry-run":
        return _setup_dry_run_output()
    if key == "gittan setup":
        return _setup_output()
    if key == "gittan status":
        return _status_output()
    if key == "gittan report":
        return "Timeframe prompt: Today selected for demo.\n\n" + _source_summary_output()
    if key == "gittan report --today --source-summary":
        return _source_summary_output()
    if key == "gittan report --today --format json":
        return _json_output()
    if key == "gittan report --today --invoice-pdf":
        return "Invoice PDF (demo stub): not generated in sandbox mode\n"
    raise ValueError(f"Unhandled allowlisted demo command in stub output: {key}")

