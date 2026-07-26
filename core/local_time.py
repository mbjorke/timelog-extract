"""Render a stored UTC stamp on the reader's own clock.

`docs/specs/timestamp-standard.md` §2: storage is UTC, but anything a person
reads renders in **their** zone with the abbreviation attached. A stamp shown in
UTC to a reader on an EEST clock is off by three hours in the direction that
makes a question about "which session was this?" unanswerable.

This lives in its own module because there are now three display surfaces
(`evidence`, `intent`, `doctor`) and the standard's own §4 makes the argument: an
idiom repeated in five places is one that belonged written down once.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

#: What to show when there is no stamp at all, rather than an empty cell.
EMPTY = "—"


def local_stamp(value: Any) -> str:
    """Format a stored stamp as local wall time with its zone abbreviation.

    Unparseable input is returned as-is rather than swallowed: a malformed stamp
    in the ledger is something the operator should see, not something a display
    helper should hide behind a dash.
    """
    text = str(value or "").strip()
    if not text:
        return EMPTY
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    return f"{parsed.astimezone():%Y-%m-%d %H:%M %Z}".strip()
