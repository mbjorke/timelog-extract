"""Export a Timely Memory local-buffer day for the ledger benchmark (GH-285 slice 2).

Automates Step 2 of docs/runbooks/timely-gittan-event-ledger-benchmark.md:
instead of manually copying memory entries from the tracker's UI, read the
locally persisted foreground-sample buffer (read-only, WAL-safe temp copy) and
write the day's entries as TSV files under ``private/benchmarks/``.

Unlike the report collector (timestamps only), this benchmark tool exports app
names, window titles, and URLs — that context is the point of the ledger diff.
Output must therefore stay in gitignored ``private/``; the script refuses to
write anywhere else unless ``--allow-outside-private`` is passed explicitly.

Usage:
  python scripts/run_timely_memory_benchmark_export.py --day 2026-07-03
  python scripts/run_timely_memory_benchmark_export.py --day 2026-07-03 \
      --tz Europe/Mariehamn --gap-seconds 30

Outputs (per day):
  private/benchmarks/timely-<DAY>-memories.tsv  spans: start/end/seconds/app/title/url
  private/benchmarks/timely-<DAY>-presence.tsv  per local hour: presence minutes

Stdlib only; does not import collector modules.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

DEFAULT_GAP_SECONDS = 30


@dataclass
class Sample:
    ts: datetime  # UTC
    app: str
    title: str
    url: str


@dataclass
class Span:
    start: datetime  # UTC
    end: datetime  # UTC, exclusive (last sample + 1s)
    app: str
    title: str
    url: str

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()


def default_db_path(home: Path) -> Path:
    return home / "Library" / "Application Support" / "com.TimelyApp.Memory" / "db.sqlite"


def _parse_utc(raw: object) -> Optional[datetime]:
    text = str(raw or "").strip().replace("T", " ")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_samples(db_path: Path, dt_from: datetime, dt_to: datetime) -> list[Sample]:
    """Read one day's samples from a WAL-safe read-only copy of the buffer."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    samples: list[Sample] = []
    try:
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(tmp.name)) as dest:
                src.backup(dest)
        with closing(sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)) as conn:
            rows = conn.execute(
                "SELECT captured_at_utc, app_name, window_title, COALESCE(details, '') "
                "FROM captured_entries "
                "WHERE captured_at_utc >= ? AND captured_at_utc < ? "
                "ORDER BY captured_at_utc",
                (
                    dt_from.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    dt_to.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            ).fetchall()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    for ts_raw, app, title, url in rows:
        ts = _parse_utc(ts_raw)
        if ts is not None and dt_from <= ts < dt_to:
            samples.append(Sample(ts=ts, app=str(app), title=str(title), url=str(url)))
    return samples


def fold_spans(samples: Iterable[Sample], gap_seconds: int = DEFAULT_GAP_SECONDS) -> list[Span]:
    """Fold ~1 Hz samples into spans; a new span starts on context change or gap."""
    spans: list[Span] = []
    current: Optional[Span] = None
    prev_ts: Optional[datetime] = None
    for s in samples:
        same_context = (
            current is not None
            and s.app == current.app
            and s.title == current.title
            and s.url == current.url
        )
        within_gap = prev_ts is not None and (s.ts - prev_ts).total_seconds() <= gap_seconds
        if current is not None and same_context and within_gap:
            current.end = s.ts + timedelta(seconds=1)
        else:
            if current is not None:
                spans.append(current)
            current = Span(start=s.ts, end=s.ts + timedelta(seconds=1), app=s.app, title=s.title, url=s.url)
        prev_ts = s.ts
    if current is not None:
        spans.append(current)
    return spans


def presence_minutes_by_local_hour(samples: Iterable[Sample], tz) -> dict[str, float]:
    """Presence minutes per local hour (each 1 Hz sample = one second)."""
    seconds: dict[str, float] = {}
    for s in samples:
        hour = s.ts.astimezone(tz).strftime("%H")
        seconds[hour] = seconds.get(hour, 0.0) + 1.0
    return {hour: round(sec / 60.0, 1) for hour, sec in sorted(seconds.items())}


def write_memories_tsv(path: Path, spans: Iterable[Span]) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["start_utc", "end_utc", "seconds", "app_name", "window_title", "url"])
        for span in spans:
            # Sanitize fields that might contain tabs or newlines for naive TSV consumers
            app_clean = span.app.replace("\t", " ").replace("\n", " ").replace("\r", " ")
            title_clean = span.title.replace("\t", " ").replace("\n", " ").replace("\r", " ")
            url_clean = span.url.replace("\t", " ").replace("\n", " ").replace("\r", " ")
            writer.writerow(
                [
                    span.start.strftime("%Y-%m-%d %H:%M:%S"),
                    span.end.strftime("%Y-%m-%d %H:%M:%S"),
                    int(span.seconds),
                    app_clean,
                    title_clean,
                    url_clean,
                ]
            )
            count += 1
    return count


def write_presence_tsv(path: Path, minutes_by_hour: dict[str, float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["local_hour", "presence_minutes"])
        for hour, minutes in minutes_by_hour.items():
            writer.writerow([hour, minutes])


def _ensure_private_out(out_dir: Path, allow_outside: bool) -> None:
    if allow_outside:
        return
    if "private" not in out_dir.parts:
        raise SystemExit(
            f"refusing to write outside private/ ({out_dir}); "
            "titles/URLs must not land in committed paths — "
            "pass --allow-outside-private to override deliberately"
        )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--day", required=True, help="local calendar day, YYYY-MM-DD")
    ap.add_argument("--tz", default=None, help="IANA timezone (default: system local)")
    ap.add_argument("--db", default=None, help="buffer path (default: standard location)")
    ap.add_argument("--out", default="private/benchmarks", help="output directory")
    ap.add_argument("--gap-seconds", type=int, default=DEFAULT_GAP_SECONDS)
    ap.add_argument("--allow-outside-private", action="store_true")
    args = ap.parse_args(argv)

    tz = ZoneInfo(args.tz) if args.tz else datetime.now().astimezone().tzinfo
    day = datetime.strptime(args.day, "%Y-%m-%d")
    dt_from = day.replace(tzinfo=tz)
    dt_to = dt_from + timedelta(days=1)

    db_path = Path(args.db).expanduser() if args.db else default_db_path(Path.home())
    if not db_path.exists():
        print(f"buffer not found: {db_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    _ensure_private_out(out_dir, args.allow_outside_private)
    out_dir.mkdir(parents=True, exist_ok=True)

    samples = read_samples(db_path, dt_from, dt_to)
    spans = fold_spans(samples, gap_seconds=args.gap_seconds)
    minutes = presence_minutes_by_local_hour(samples, tz)

    memories_path = out_dir / f"timely-{args.day}-memories.tsv"
    presence_path = out_dir / f"timely-{args.day}-presence.tsv"
    span_count = write_memories_tsv(memories_path, spans)
    write_presence_tsv(presence_path, minutes)

    total_hours = round(len(samples) / 3600.0, 2)
    print(f"day {args.day} ({tz}): {len(samples)} samples -> {span_count} spans")
    print(f"presence total: {total_hours}h")
    print(f"wrote {memories_path}")
    print(f"wrote {presence_path}")
    print(
        "next (runbook Step 1): "
        f"gittan report --from {args.day} --to {args.day} --format json "
        f"--json-file private/benchmarks/gittan-{args.day}.json --source-summary"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
