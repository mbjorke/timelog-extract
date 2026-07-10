"""Shared helpers for asserting on Rich-rendered CLI output.

Rich emits ANSI SGR color/style codes when it detects a color-capable
terminal, which breaks plain-substring assertions. Test modules should use
``strip_ansi`` instead of defining a local copy of this regex.
"""

from __future__ import annotations

import re

ANSI_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(output: str) -> str:
    """Strip ANSI SGR escape sequences from Rich-rendered CLI output."""
    return ANSI_SGR_RE.sub("", output)
