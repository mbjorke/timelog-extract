"""Backward-compatible wrapper; prefer `core.live_terminal.contract`."""

from core.live_terminal.contract import (
    DEMO_SANDBOX_DENIED_MESSAGE,
    normalize_demo_command_line,
    is_allowlisted_demo_command,
    validate_demo_command,
)

__all__ = [
    "DEMO_SANDBOX_DENIED_MESSAGE",
    "normalize_demo_command_line",
    "is_allowlisted_demo_command",
    "validate_demo_command",
]
