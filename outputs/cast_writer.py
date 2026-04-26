"""Gittan semantic cast writer — asciicast v3 + 'g' events.

Each event line in the .cast file is one of:
  [t, "o", "plain text\\r\\n"]   — raw fallback; asciinema play uses these
  [t, "g", {"t": "type", ...}]  — semantic event; Gittan player uses these

The Gittan player renders "g" events with design tokens (honey for hours,
success-green for ✓, etc.). A standard asciinema player ignores "g" lines
and falls back to the paired "o" lines.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CastWriter:
    """Accumulate semantic cast events and write a .cast file."""

    path: str | Path
    title: str = "gittan session"
    width: int = 120
    height: int = 40
    event_step: float = 0.7
    realtime: bool = False

    _events: list[tuple[float, str, Any]] = field(default_factory=list, init=False)
    _t0: float = field(default_factory=time.time, init=False)
    _cursor: float = field(default=0.0, init=False)

    def _t(self) -> float:
        if self.realtime:
            return round(time.time() - self._t0, 3)
        t = round(self._cursor, 3)
        self._cursor += self.event_step
        return t

    def _g(self, payload: dict[str, Any], *, text: str = "") -> None:
        t = self._t()
        self._events.append((t, "g", payload))
        if text:
            self._events.append((t, "o", text + "\r\n"))

    def _plain_table(self, cols: list[dict[str, str]], rows: list[dict[str, Any]]) -> str:
        labels = [str(col.get("label", "")) for col in cols]
        data = [[str(cell) for cell in row.get("cells", [])] for row in rows]
        widths = [
            max(len(labels[idx]), *(len(row[idx]) for row in data if idx < len(row)))
            for idx in range(len(labels))
        ]

        def fmt(values: list[str]) -> str:
            rendered = []
            for idx, value in enumerate(values):
                align = cols[idx].get("align", "left") if idx < len(cols) else "left"
                rendered.append(value.rjust(widths[idx]) if align == "right" else value.ljust(widths[idx]))
            return "  ".join(rendered)

        lines = [fmt(labels), fmt(["-" * width for width in widths])]
        for row in data:
            lines.append(fmt(row[:len(labels)] + [""] * max(0, len(labels) - len(row))))
        return "\n".join(lines)

    # ── Semantic emitters ──────────────────────────────────────────────

    def prompt(self, cmd: str | None = None) -> None:
        user = os.environ.get("USER", "user")
        cwd = Path.cwd().name
        self._g(
            {"t": "prompt", "user": user, "dir": cwd, "cmd": cmd},
            text=f"{user}@{cwd} % {cmd or ''}",
        )

    def question(self, text: str, answer: str) -> None:
        self._g(
            {"t": "question", "text": text, "answer": answer},
            text=f"? {text}  {answer}",
        )

    def bee_box(self, title: str, lines: list[str]) -> None:
        fallback_lines = [
            f"  __   {title}",
            " /oo\\",
            *[
                f" \\__/  {line}" if idx == 0 else f"      {line}"
                for idx, line in enumerate(lines)
            ],
        ]
        self._g(
            {"t": "bee-box", "title": title, "lines": lines},
            text="\n".join(fallback_lines),
        )

    def status_line(self, text: str) -> None:
        self._g({"t": "status-line", "text": text}, text=text)

    def heading(self, text: str) -> None:
        self._g({"t": "heading", "text": text}, text=text)

    def caption(self, text: str, center: bool = False) -> None:
        self._g({"t": "caption", "text": text, "center": center}, text=text)

    def table(
        self,
        cols: list[dict[str, str]],
        rows: list[dict[str, Any]],
    ) -> None:
        self._g({"t": "table", "cols": cols, "rows": rows}, text=self._plain_table(cols, rows))

    def health_table(self, rows: list[dict[str, str]]) -> None:
        cols = [
            {"label": "Source / Path", "align": "left"},
            {"label": "Status", "align": "left"},
            {"label": "Details", "align": "left"},
        ]
        table_rows = [
            {"cells": [row.get("source", ""), row.get("status", ""), row.get("detail", "")]}
            for row in rows
        ]
        self._g({"t": "health-table", "rows": rows}, text=self._plain_table(cols, table_rows))

    def note(self, text: str) -> None:
        self._g({"t": "note", "text": text}, text=f"Note: {text}")

    def next_steps(self, items: list[str]) -> None:
        self._g(
            {"t": "next-steps", "items": items},
            text="Next steps\n" + "\n".join(f"– {i}" for i in items),
        )

    def blank(self) -> None:
        self._g({"t": "blank"})

    def pause(self, seconds: float) -> None:
        """Insert a timing gap without any output."""
        if self.realtime:
            time.sleep(seconds)
        else:
            self._cursor += seconds

    # ── Persist ───────────────────────────────────────────────────────

    def save(self) -> Path:
        p = Path(self.path)
        header: dict[str, Any] = {
            "version": 3,
            "width": self.width,
            "height": self.height,
            "gittan": "1.0",
            "title": self.title,
            "duration": max((t for t, _, _ in self._events), default=0.0),
        }
        with p.open("w", encoding="utf-8") as f:
            f.write(json.dumps(header, ensure_ascii=False) + "\n")
            for t, kind, payload in self._events:
                f.write(json.dumps([t, kind, payload], ensure_ascii=False) + "\n")
        return p

    @property
    def event_count(self) -> int:
        return sum(1 for _, kind, _ in self._events if kind == "g")
