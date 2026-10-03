#!/usr/bin/env python3
"""Measure what Grok actually exposes locally, before any collector is designed.

Answers Q1 of ``docs/specs/project-field-detection-signals.md``: does the Grok
**Project** name reach anything Gittan can read on this machine — the URL path,
the tab title, or neither? The survey deliberately records the Project field as
*unavailable* rather than *pending* until this has been run against real data.

Read-only. It copies each browser History database before querying it (the same
guard ``collectors/chrome.py`` uses), touches nothing else, and writes no files.

**Output is safe to paste.** Conversation ids, titles and URLs are never
printed: the report is path *shapes*, counts, and structural facts about titles.
``--show-samples N`` prints redacted samples for local eyes only — do not paste
that output anywhere.

Usage:
    python scripts/measure_grok_surface.py
    python scripts/measure_grok_surface.py --json          # machine-readable
    python scripts/measure_grok_surface.py --show-samples 5
    python scripts/measure_grok_surface.py --days 180      # default: all history
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from collectors.chrome import query_chrome  # noqa: E402

#: Hosts that serve a Grok conversation. ``x.com`` is included because Grok is
#: also reachable inside X, and that surface may carry a different URL shape.
#: These are SQL prefilters only — a ``LIKE`` matches the string anywhere, so
#: ``notgrok.com.example`` or a URL carrying one as a query parameter would
#: otherwise enter the sample and could even trigger the project-route verdict.
#: :func:`is_grok_url` checks the parsed host and route afterwards.
GROK_HOSTS = ("grok.com", "x.com/i/grok", "twitter.com/i/grok")

#: Hosts where Grok lives under a route rather than owning the whole domain.
_GROK_ROUTE_HOSTS = {"x.com": "/i/grok", "twitter.com": "/i/grok"}

#: Chromium-family browsers share the History schema, so one query covers them
#: all. Listing them separately matters for a null result: "no Grok visits" and
#: "no readable browser" are different answers, and only one of them means the
#: Project field is unavailable.
CHROMIUM_ROOTS = {
    "Chrome": "Google/Chrome",
    "Chrome Beta": "Google/Chrome Beta",
    "Chrome Canary": "Google/Chrome Canary",
    "Chromium": "Chromium",
    "Brave": "BraveSoftware/Brave-Browser",
    "Edge": "Microsoft Edge",
    "Arc": "Arc/User Data",
    "Vivaldi": "Vivaldi",
    "Opera": "com.operasoftware.Opera",
}

#: Local application-data directories a Grok desktop build would plausibly use.
APP_DIR_HINTS = ("grok", "xai", "x.ai")

_CHROME_EPOCH_DELTA_US = 11_644_473_600_000_000

#: A path segment that looks like an opaque identifier rather than a route name.
_ID_RE = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"  # uuid
    r"|[0-9a-zA-Z_-]{16,}"                                                # opaque
    r"|\d{6,})$"                                                          # numeric
)

#: Route words a chat host uses. Anything else in a path is redacted, so this
#: list is the whole vocabulary the reported shapes can contain.
_KNOWN_ROUTES = frozenset(
    {
        "c", "chat", "chats", "conversation", "thread", "threads",
        "project", "projects", "p", "workspace", "folder",
        "i", "grok", "share", "new", "app", "home",
    }
)
#: Routes whose following id names *this conversation* rather than its container.
_CONVERSATION_ROUTES = frozenset({"c", "chat", "chats", "conversation", "thread"})

_TITLE_SEPARATORS = (" — ", " – ", " | ", " · ", " - ")

#: Below this many conversations, a segment present on every one of them cannot
#: be told apart from a Project label that happens to cover the whole sample.
#: Claiming "branding" there would turn a thin sample into a false negative.
_AMBIGUITY_FLOOR = 5


def is_grok_url(url: str) -> bool:
    """True only when the *parsed* host (and route, where shared) is Grok's."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url or "")
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host == "grok.com" or host.endswith(".grok.com"):
        return True
    route = _GROK_ROUTE_HOSTS.get(host)
    path = (parsed.path or "").lower()
    return bool(route and (path == route or path.startswith(route + "/")))


def profile_history_paths(home: Path) -> List[Tuple[str, Path]]:
    """``[(browser, History path)]`` for every Chromium-family profile found."""
    support = home / "Library" / "Application Support"
    found: List[Tuple[str, Path]] = []
    for browser, rel in CHROMIUM_ROOTS.items():
        root = support / rel
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if child.name != "Default" and not child.name.startswith(
                ("Profile ", "Guest Profile")
            ):
                continue
            history = child / "History"
            if history.is_file():
                found.append((browser, history))
    return found


def profile_readable(history_path: Path) -> bool:
    """True when this History database can actually be copied and queried.

    ``query_chrome`` swallows copy and SQL errors and returns ``[]``, which is
    indistinguishable from a history holding no Grok visits. Counting an
    unreadable profile as readable turned ``INCONCLUSIVE`` into ``NO DATA`` —
    the one distinction this script exists to keep.
    """
    import shutil
    import sqlite3
    import tempfile

    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    try:
        shutil.copy2(history_path, handle.name)
        conn = sqlite3.connect(handle.name)
        try:
            conn.execute("SELECT 1 FROM urls LIMIT 1").fetchone()
        finally:
            conn.close()
        return True
    except (OSError, sqlite3.Error):
        return False
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


def fetch_rows(
    home: Path, days: int | None
) -> Tuple[List[Tuple[int, str, str]], List[str], List[str], List[str]]:
    """``(rows, browsers_readable, browsers_with_hits, browsers_unreadable)``."""
    if days:
        start = datetime.now(timezone.utc) - timedelta(days=days)
    else:
        start = datetime(1990, 1, 1, tzinfo=timezone.utc)
    start_cu = int(start.timestamp() * 1_000_000) + _CHROME_EPOCH_DELTA_US
    end_cu = int(
        (datetime.now(timezone.utc) + timedelta(days=1)).timestamp() * 1_000_000
    ) + _CHROME_EPOCH_DELTA_US

    where = " OR ".join("LOWER(u.url) LIKE ?" for _ in GROK_HOSTS)
    params = tuple(f"%{host}%" for host in GROK_HOSTS)

    rows: List[Tuple[int, str, str]] = []
    readable: List[str] = []
    unreadable: List[str] = []
    with_hits: List[str] = []
    for browser, path in profile_history_paths(home):
        if not profile_readable(path):
            if browser not in unreadable:
                unreadable.append(browser)
            continue
        if browser not in readable:
            readable.append(browser)
        # The SQL LIKE is a prefilter; the parsed host is the actual test.
        got = [row for row in query_chrome(path, where, start_cu, end_cu, params)
               if is_grok_url(row[1] or "")]
        if got:
            rows.extend(got)
            if browser not in with_hits:
                with_hits.append(browser)
    return rows, readable, with_hits, unreadable


def path_shape(url: str) -> Tuple[str, str | None]:
    """``(templated path, conversation id)`` — ``grok.com/c/<id>`` from a chat URL.

    Every segment that is not a **known route word** is replaced, not kept. A
    short segment that no id pattern matches is exactly where a project or
    customer name sits (``/project/Acme/c/…``), and both output formats print the
    shape — so keeping it verbatim would leak the name this script exists to
    avoid printing. Known routes survive because the shape is worthless without
    them.

    The conversation id is the one that follows a **conversation** route, not the
    first id in the path. For ``/project/<pid>/c/<cid>`` the first id is the
    project's; using it collapsed every chat in a project into one conversation
    and made their differing titles look like one renamed thread, which is the
    measurement this script is for.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    segments = [s for s in (parsed.path or "").split("/") if s]
    shaped: List[str] = []
    ids: List[Tuple[str, str | None]] = []  # (id, preceding route word)
    previous_route: str | None = None
    for segment in segments:
        if _ID_RE.match(segment):
            shaped.append("<id>")
            ids.append((segment, previous_route))
            previous_route = None
            continue
        lowered = segment.lower()
        if lowered in _KNOWN_ROUTES:
            shaped.append(lowered)
            previous_route = lowered
        else:
            shaped.append("<seg>")
            previous_route = None

    conversation_id: str | None = None
    for value, route in ids:
        if route in _CONVERSATION_ROUTES:
            conversation_id = value
    if conversation_id is None and len(ids) == 1 and ids[0][1] is None:
        # A bare ``/<id>`` with no route word: the only id, and nothing says it
        # belongs to a project, so it is this conversation.
        conversation_id = ids[0][0]
    return f"{host}/{'/'.join(shaped)}" if shaped else host, conversation_id


def split_title(title: str) -> List[str]:
    """Title split on the separators chat UIs use for ``A — B`` style labels."""
    for sep in _TITLE_SEPARATORS:
        if sep in title:
            return [part.strip() for part in title.split(sep) if part.strip()]
    return [title.strip()] if title.strip() else []


def analyse(rows: List[Tuple[int, str, str]]) -> Dict[str, Any]:
    """Structural facts only — no ids, urls or titles in the result."""
    shapes: Counter = Counter()
    ids_per_shape: Dict[str, set] = defaultdict(set)
    titles_by_id: Dict[str, set] = defaultdict(set)
    segment_ids: Dict[str, set] = defaultdict(set)
    titled = 0
    first_seen: int | None = None
    last_seen: int | None = None

    for visit_time, url, title in rows:
        shape, conversation_id = path_shape(url or "")
        shapes[shape] += 1
        if conversation_id:
            ids_per_shape[shape].add(conversation_id)
        first_seen = visit_time if first_seen is None else min(first_seen, visit_time)
        last_seen = visit_time if last_seen is None else max(last_seen, visit_time)

        clean = (title or "").strip()
        if not clean:
            continue
        titled += 1
        key = conversation_id or url
        titles_by_id[key].add(clean)
        for part in split_title(clean):
            segment_ids[part].add(key)

    # The Q1 test. A Grok Project groups several chats, so a title segment that
    # appears across *several distinct conversations* but not across all of them
    # behaves like a Project label. A segment on every conversation is branding
    # ("Grok"); a segment on exactly one is that chat's own title.
    total_conversations = len(titles_by_id)
    grouping = {
        segment: len(keys)
        for segment, keys in segment_ids.items()
        if 1 < len(keys) < max(total_conversations, 2)
    }
    branding = sorted(
        segment
        for segment, keys in segment_ids.items()
        if total_conversations > 1 and len(keys) == total_conversations
    )

    return {
        "visits": len(rows),
        "visits_with_title": titled,
        "conversations": total_conversations,
        "first_seen": _iso(first_seen),
        "last_seen": _iso(last_seen),
        "path_shapes": [
            {"shape": shape, "visits": count, "distinct_ids": len(ids_per_shape[shape])}
            for shape, count in shapes.most_common()
        ],
        "titled_conversations": len([k for k, v in titles_by_id.items() if v]),
        "project_like_title_segments": sorted(
            grouping.items(), key=lambda kv: (-kv[1], kv[0])
        )[:10],
        "constant_title_segments": branding,
    }


def _iso(visit_time: int | None) -> str | None:
    if not visit_time:
        return None
    seconds = (visit_time - _CHROME_EPOCH_DELTA_US) / 1_000_000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()


def find_app_dirs(home: Path) -> List[Dict[str, Any]]:
    """Local application-data directories that look like a Grok desktop build."""
    out: List[Dict[str, Any]] = []
    for base in (
        home / "Library" / "Application Support",
        home / "Library" / "Containers",
        home / "Library" / "Preferences",
    ):
        if not base.is_dir():
            continue
        try:
            children = sorted(base.iterdir())
        except PermissionError:
            continue
        for child in children:
            name = child.name.lower()
            hit = next((hint for hint in APP_DIR_HINTS if hint in name), None)
            if hit:
                # The directory *name* is reported as the hint it matched and the
                # library it sits in — never verbatim. `grok-Acme` matching here
                # would otherwise print a customer name in the default report.
                out.append({"library": base.name, "hint": hit, "is_dir": child.is_dir()})
    return out


def verdict(report: Dict[str, Any]) -> str:
    """The answer Q1 asks for, in one line."""
    if not report["browsers_seen"]:
        if report.get("browsers_unreadable"):
            return (
                "INCONCLUSIVE — %d browser(s) were found but their history could "
                "not be read, so this says nothing about Grok."
                % len(report["browsers_unreadable"])
            )
        return (
            "INCONCLUSIVE — no Chromium-family browser data was readable, so "
            "this says nothing about Grok."
        )
    if not report["visits"]:
        return (
            "NO DATA — browsers were readable but hold no Grok visits. Either "
            "Grok is used in a browser this script cannot read (Safari), or the "
            "history window has rotated."
        )
    url_project = [
        s["shape"] for s in report["path_shapes"] if "project" in s["shape"].lower()
    ]
    if url_project:
        return (
            "URL CARRIES A PROJECT ROUTE — %s. The Project is addressable, so an "
            "app_project anchor is worth building (survey R3)." % ", ".join(url_project)
        )
    if report["project_like_title_segments"]:
        return (
            "TITLE MAY CARRY THE PROJECT — %d title segment(s) group several "
            "conversations without covering all of them. Inspect them with "
            "--show-samples before trusting it; a shared segment can also be a "
            "recurring topic." % len(report["project_like_title_segments"])
        )
    if report["constant_title_segments"] and report["conversations"] < _AMBIGUITY_FLOOR:
        return (
            "AMBIGUOUS — every one of the %d conversation(s) shares a title "
            "segment. That is what branding looks like, and also what a Project "
            "covering the whole sample looks like. Too few conversations to "
            "separate them; re-run with a wider history or read them with "
            "--show-samples." % report["conversations"]
        )
    if report["titled_conversations"] < _AMBIGUITY_FLOOR and not report["project_like_title_segments"]:
        return (
            "INSUFFICIENT TITLES — only %d conversation(s) carry a title, which "
            "cannot support ruling the title out as a Project signal. Widen the "
            "history window (--days) or use Grok more before trusting a negative."
            % report["titled_conversations"]
        )
    if report["constant_title_segments"]:
        return (
            "PROJECT NOT OBSERVABLE — no project route in the URL, and the only "
            "shared title text is on all %d conversations, which reads as "
            "branding. Treat the Project field as unavailable and bind on the "
            "thread id instead (survey I1)." % report["conversations"]
        )
    return (
        "PROJECT NOT OBSERVABLE — no project route in the URL and no title "
        "segment that groups conversations. Treat the Project field as "
        "unavailable and bind on the thread id instead (survey I1)."
    )


def render(report: Dict[str, Any]) -> str:
    lines = ["Grok local surface — measurement", ""]
    lines.append(f"Browsers readable : {', '.join(report['browsers_seen']) or 'none'}")
    if report.get("browsers_unreadable"):
        lines.append(
            f"Found but UNREADABLE: {', '.join(report['browsers_unreadable'])} "
            "— these say nothing either way"
        )
    lines.append(f"With Grok visits  : {', '.join(report['browsers_with_hits']) or 'none'}")
    lines.append(f"Visits            : {report['visits']} ({report['visits_with_title']} with a title)")
    lines.append(f"Conversations     : {report['conversations']}")
    if report["first_seen"]:
        lines.append(f"History window    : {report['first_seen']} → {report['last_seen']}")
    lines.append("")

    if report["path_shapes"]:
        lines.append("URL path shapes")
        for shape in report["path_shapes"]:
            lines.append(
                f"  {shape['visits']:>5}  {shape['shape']}"
                + (f"   ({shape['distinct_ids']} distinct ids)" if shape["distinct_ids"] else "")
            )
        lines.append("")

    segments = report["project_like_title_segments"]
    lines.append("Title segments that group several conversations")
    if segments:
        for segment, count in segments:
            lines.append(
                f"  {count:>5} conversations share a segment of {len(segment)} chars"
            )
        lines.append("  (run with --show-samples to read them locally)")
    else:
        lines.append("  none — no title text is shared across conversations")
    lines.append("")

    if report["constant_title_segments"]:
        lengths = ", ".join(f"{len(s)} chars" for s in report["constant_title_segments"])
        lines.append(
            f"On every title    : {len(report['constant_title_segments'])} segment(s) "
            f"({lengths}) — branding, or a project covering the whole sample"
        )
    lines.append(
        "Retitled threads  : not measurable here. Chromium stores the title on "
        "the URL row, so every visit to one URL reports that URL's *current* "
        "title and a rename leaves no trace. Q2 needs a source that keeps "
        "per-visit titles."
    )
    lines.append("")
    lines.append("Local app data")
    if report["app_dirs"]:
        for entry in report["app_dirs"]:
            lines.append(
                f"  1 entry matching {entry['hint']!r} under "
                f"~/Library/{entry['library']}"
                + ("/" if entry["is_dir"] else " (file)")
            )
    else:
        lines.append("  none found — no Grok desktop build writes here")
    lines.append("")
    lines.append("Verdict: " + report["verdict"])
    return "\n".join(lines)


def _json_payload(report: Dict[str, Any], show_samples: int) -> Dict[str, Any]:
    """The report as JSON — segment text stripped unless explicitly requested.

    Segment text is the one field that can carry a customer name, and JSON is
    the form most likely to be pasted somewhere. It leaves the process only when
    the operator asks for it.
    """
    if show_samples:
        # The flag is an opt-in to *samples*, not to everything: N bounds both
        # lists here exactly as it bounds the printed ones.
        payload = dict(report)
        payload["project_like_title_segments"] = report["project_like_title_segments"][:show_samples]
        payload["constant_title_segments"] = report["constant_title_segments"][:show_samples]
        payload["segments_redacted"] = False
        payload["contains_samples"] = True
        return payload
    payload = dict(report)
    payload["project_like_title_segments"] = [
        [len(segment), count] for segment, count in report["project_like_title_segments"]
    ]
    payload["constant_title_segments"] = [
        len(segment) for segment in report["constant_title_segments"]
    ]
    payload["segments_redacted"] = True
    return payload


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=0, help="Limit to the last N days (default: all history).")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    parser.add_argument(
        "--show-samples",
        type=int,
        default=0,
        metavar="N",
        help="Print up to N candidate title segments in clear. Local eyes only — do not paste.",
    )
    parser.add_argument("--home", default=None, help="Override the home directory (testing).")
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser() if args.home else Path.home()
    rows, readable, with_hits, unreadable = fetch_rows(home, args.days or None)
    report = analyse(rows)
    report["browsers_seen"] = readable
    report["browsers_with_hits"] = with_hits
    report["browsers_unreadable"] = unreadable
    report["app_dirs"] = find_app_dirs(home)
    report["verdict"] = verdict(report)

    if args.json:
        print(json.dumps(_json_payload(report, args.show_samples), indent=2, sort_keys=True))
        return 0

    # render() reports lengths and counts only, never segment text.
    print(render(report))
    if args.show_samples:
        print("\nCandidate segments (local only, do not paste):")
        for segment, count in report["project_like_title_segments"][: args.show_samples]:
            print(f"  {count:>3} conversations · {segment!r}")
        for segment in report["constant_title_segments"][: args.show_samples]:
            print(f"  all conversations · {segment!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
