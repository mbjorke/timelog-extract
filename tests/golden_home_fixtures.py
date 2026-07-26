"""Materialize synthetic source data into a temporary HOME (not a test module).

A golden dataset may declare ``home_fixtures``: a list of specs, each naming a
materializer by ``kind``. Each materializer writes one collector's on-disk shape
into a throwaway HOME, so the full report path can be measured against
fabricated data — no real local data, no network.

Kinds:

``cursor_composer_headers``
    Cursor ``state.vscdb`` ``ItemTable`` row (the GH-348 label guards).
``chrome_history``
    Chrome History SQLite (``urls`` + ``visits``) for one browser profile.

Chrome visits arrive either as literal rows (``visits``) or as a deterministic
series (``synth``) — evenly spaced visits over a window, which is the on-disk
shape of sustained single-host work (GH-414). ``synth`` is reproducible without
a seed: spacing is ``span_minutes / count``, so visit *i* lands at
``start + i * step`` and the last one sits one step short of the full span.

Consumed by ``scripts/run_golden_eval.py``; importable from unit tests, which
run with ``tests/`` on ``sys.path``.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from chrome_test_support import EPOCH_DELTA_US, make_chrome_db

Visit = tuple[datetime, str, str]


def _parse_ts(value: str) -> datetime:
    """Parse an ISO timestamp; a trailing ``Z`` means UTC, naive means UTC."""
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def chrome_synth_visits(synth: dict[str, Any]) -> list[Visit]:
    """Build an evenly spaced visit series from a ``synth`` spec.

    ``url_template`` / ``title_template`` may use ``{i}`` (visit index).
    """
    count = int(synth["count"])
    if count < 1:
        return []
    start = _parse_ts(synth["start"])
    step = timedelta(minutes=float(synth.get("span_minutes", 0))) / count
    url_template = str(synth["url_template"])
    title_template = str(synth.get("title_template", synth.get("title", "")))
    return [
        (start + step * i, url_template.format(i=i), title_template.format(i=i))
        for i in range(count)
    ]


def _literal_visits(rows: Iterable[dict[str, Any]]) -> list[Visit]:
    return [
        (_parse_ts(row["at"]), str(row["url"]), str(row.get("title", "")))
        for row in rows
    ]


def _insert_visits(db_path: Path, visits: Sequence[Visit]) -> None:
    """Insert visits, reusing one ``urls`` row per distinct URL as Chrome does."""
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        url_ids: dict[str, int] = {}
        for ts, url, title in visits:
            url_id = url_ids.get(url)
            if url_id is None:
                cur.execute("INSERT INTO urls (url, title) VALUES (?, ?)", (url, title))
                url_id = int(cur.lastrowid)
                url_ids[url] = url_id
            visit_time_cu = int(ts.timestamp() * 1_000_000) + EPOCH_DELTA_US
            cur.execute(
                "INSERT INTO visits (url, visit_time) VALUES (?, ?)",
                (url_id, visit_time_cu),
            )
        conn.commit()
    finally:
        conn.close()


def materialize_chrome_history(home: Path, spec: dict[str, Any], root: Path) -> None:
    """Write a Chrome History DB for one profile into *home*."""
    _ = root
    profile = str(spec.get("profile", "Default"))
    history_dir = home / "Library" / "Application Support" / "Google" / "Chrome" / profile
    history_dir.mkdir(parents=True, exist_ok=True)
    db_path = history_dir / "History"
    make_chrome_db(db_path)

    visits: list[Visit] = []
    if spec.get("synth"):
        visits.extend(chrome_synth_visits(spec["synth"]))
    if spec.get("visits"):
        visits.extend(_literal_visits(spec["visits"]))
    if not visits:
        raise ValueError("chrome_history fixture needs 'synth' or 'visits'")
    _insert_visits(db_path, sorted(visits, key=lambda v: v[0]))


def materialize_cursor_composer_headers(
    home: Path, spec: dict[str, Any], root: Path
) -> None:
    """Write Cursor's ``state.vscdb`` with one ``composer.composerHeaders`` row."""
    rel = str(spec.get("path") or "").strip()
    if not rel:
        raise ValueError("cursor_composer_headers fixture needs 'path'")
    payload = json.loads((root / rel).read_text(encoding="utf-8"))
    cursor_dir = home / "Library" / "Application Support" / "Cursor"
    db_dir = cursor_dir / "User" / "globalStorage"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_dir / "state.vscdb"))
    try:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO ItemTable VALUES (?, ?)",
            ("composer.composerHeaders", json.dumps(payload)),
        )
        conn.commit()
    finally:
        conn.close()
    # collect_cursor() skips composer reads when the logs dir is missing.
    (cursor_dir / "logs").mkdir(parents=True, exist_ok=True)


MATERIALIZERS: dict[str, Callable[[Path, dict[str, Any], Path], None]] = {
    "chrome_history": materialize_chrome_history,
    "cursor_composer_headers": materialize_cursor_composer_headers,
}


def materialize_home(specs: Sequence[dict[str, Any]], root: Path) -> Path:
    """Create a temp HOME, apply every spec, and return its path.

    The caller owns the directory and must remove it.
    """
    home = Path(tempfile.mkdtemp(prefix="golden_home_"))
    try:
        for spec in specs:
            kind = str(spec.get("kind") or "").strip()
            materializer = MATERIALIZERS.get(kind)
            if materializer is None:
                raise ValueError(
                    f"unknown home fixture kind {kind!r} "
                    f"(known: {', '.join(sorted(MATERIALIZERS))})"
                )
            materializer(home, spec, root)
    except BaseException:
        # A half-built home has no owner — the caller never saw the path.
        shutil.rmtree(home, ignore_errors=True)
        raise
    return home
