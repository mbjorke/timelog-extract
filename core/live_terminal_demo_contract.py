"""Live terminal sandbox demo — P0 command contract (allowlist + denial copy).

Single source of truth for `docs/specs/live-terminal-sandbox-demo.md` § Command contract.
Server-side enforcement must import this module; do not duplicate lists in handlers.
"""

from __future__ import annotations

import re
from typing import Final, Tuple

# Spec § "Any other input returns"
DEMO_SANDBOX_DENIED_MESSAGE: Final[str] = "Command not allowed in demo sandbox. Try: help"

# Canonical allowlist after normalization (lowercase, single spaces, stripped).
_ALLOWED_NORMALIZED: Final[frozenset[str]] = frozenset(
    {
        "gittan doctor",
        "gittan report --today --source-summary",
        "gittan report --today --format json",
        "gittan report --today --invoice-pdf",
        "help",
        "clear",
    }
)


def normalize_demo_command_line(line: str) -> str:
    """Strip, collapse internal whitespace, lowercase — for safe comparison only."""
    s = (line or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def is_allowlisted_demo_command(line: str) -> bool:
    """True iff the normalized input matches the v1 allowlist (spec)."""
    return normalize_demo_command_line(line) in _ALLOWED_NORMALIZED


def validate_demo_command(line: str) -> Tuple[bool, str]:
    """Return (allowed, message). When denied, message is DEMO_SANDBOX_DENIED_MESSAGE."""
    if is_allowlisted_demo_command(line):
        return True, ""
    return False, DEMO_SANDBOX_DENIED_MESSAGE
