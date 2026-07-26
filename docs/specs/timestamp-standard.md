# Timestamp standard — storage, display, and parsing

Status: active
Last updated: 2026-07-26
Owner: Maintainer + active agents

Gittan's whole output is timestamps turned into hours, so how they are stored,
shown and parsed is load-bearing. Until now the rules existed in three places
that did not talk to each other: `source-collector-contract.md` said only
"normalize timestamps consistently with the runtime timezone policy" without
naming the policy; the parsing performance findings lived in `.jules/bolt.md`, an
agent's own journal; and the display rule existed nowhere, which is how a
human-facing prompt shipped showing UTC to a reader on an EEST clock.

This is the one place. Three rules, then the parsing detail that actually bites.

## 1. Store UTC, timezone-aware, with an explicit offset

Every durable record — the evidence ledger, the intent log, the observed cache,
reported time — stores an ISO-8601 timestamp in **UTC with an offset**
(`2026-07-26T10:10:00+00:00`), never a bare local time and never a `Z` suffix in
our own writes (see §4 for why `Z` is a parsing hazard on the supported floor).

A **naive** datetime reaching storage is a bug. Where one can arrive from an
external source, assume UTC *explicitly* and in one place:

```python
if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
```

## 2. Show the reader's clock, with the zone named

A stored stamp is for records; a displayed stamp is for a human deciding
something. Those are different jobs. Anything a person reads renders in **their**
zone with the abbreviation attached:

```
stored   2026-07-26T10:10:00+00:00
shown    2026-07-26 13:10 EEST
```

The abbreviation is not decoration. Åland runs EET (UTC+2) in winter and EEST
(UTC+3) in summer, so `13:10` alone is ambiguous about which rule applied — and
`10:10` would be simply wrong on a July wall clock.

Why this is a rule and not a preference: `gittan intent` asks *"which project was
this session?"*. A session the operator lived at 13:10 shown as 10:10 is not a
slightly-off label, it is an unanswerable question that looks authoritative.
Found in review 2026-07-26, fixed at both reading points
(`core/cli_intent.py`, `core/cli_evidence.py::_local_stamp`).

## 3. Session math stays in the runtime timezone

Day grouping and session spans use the runtime local timezone
(`core/analytics.py::group_by_day`, `get_date_range`), because a working day is a
local concept. Storage stays UTC regardless. Do not "simplify" one into the other.

## 4. Parsing: `fromisoformat`, and the floor that constrains it

`datetime.fromisoformat` is dramatically faster than `strptime`, which recompiles
a format and touches locale on every call. Measured in this repo, 200k iterations:

| Input | `strptime` | Alternative | Gain |
|---|---|---|---|
| `2026-07-26 10:10` | 0.988s | `fromisoformat` 0.029s | **33.6x** |
| `20260709T162324` (compact) | 0.853s | manual int slicing 0.128s | **6.6x** |

Consistent with the gains Jules Bolt recorded when converting the hot paths
(`.jules/bolt.md`): ~4.4–6.0x on IDE log lines (#401), ~32–37x on core date
parsing (#420), ~11.6x on Cursor log folder names (#456), ~1.74x on `group_by_day`
aggregation (#432).

**But `fromisoformat` is not universal on the supported floor.** `pyproject.toml`
declares `>=3.10` and CI tests 3.10 and 3.12. Verified on both interpreters:

| Input | 3.10 | 3.12 |
|---|---|---|
| `2026-07-26 10:10` | OK | OK |
| `2026-07-26T10:10:00.123456+00:00` | OK | OK |
| `2026-07-26T10:10:00Z` | **ValueError** | OK |
| `20260709T162324` (compact) | **ValueError** | OK |

Python 3.11 relaxed the parser to accept most ISO-8601 including basic format and
the `Z` suffix. On 3.10 it accepts only what `isoformat()` emits. So:

**Normalize `Z` before parsing.** Every site that reads an external stamp already
does this — GitHub returns `Z` suffixes, so do Claude transcripts:

```python
if text.endswith("Z"):
    text = text[:-1] + "+00:00"
parsed = datetime.fromisoformat(text)
```

Audited 2026-07-26: `collectors/github.py::_parse_github_ts`,
`core/gh_repo_discovery.py`, `collectors/cursor.py`,
`collectors/cursor_agent_turns.py`, `collectors/vscode_fork.py` and
`core/git_activity_discovery.py` all handle it. **No live 3.10 defect was found** —
the idiom is correct in five copies, which is exactly why it belongs written down
once.

**Use manual integer slicing for compact formats.** `20260709T162324` cannot go
through `fromisoformat` on 3.10 at all, so Bolt's choice in
`collectors/cursor_log_scan.py` is not only 6.6x faster than `strptime`, it is the
only floor-safe option:

```python
datetime.date(int(name[:4]), int(name[4:6]), int(name[6:8]))
```

`.jules/bolt.md` records the speed reason but not the compatibility one. A future
optimisation pass that "simplifies" this to `fromisoformat` would pass locally on
3.11+ and break the 3.10 CI job.

**Slice long stamps to 26 characters.** Log lines with more than microsecond
precision fail `fromisoformat`; truncating caps at microseconds
(`collectors/cursor_agent_turns.py`, `collectors/vscode_fork.py`).

## Remaining opportunity

`collectors/timelog.py` still parses with `strptime` in three places (lines 26,
36, 78). Its format `%Y-%m-%d %H:%M` **is** `fromisoformat`-safe on 3.10
(verified above), so the ~33x gain is available with no compatibility risk. Not
done here: this doc is the standard, not the conversion, and the worklog collector
reads a file the operator hand-edits — worth its own change with its own tests.

## Checklist for a new collector or a display surface

- Storing a stamp → UTC, tz-aware, offset form. Naive input gets `timezone.utc`
  explicitly.
- Showing a stamp to a human → convert with `astimezone()` and print the zone.
- Parsing an external stamp → strip `Z` to `+00:00` first, then `fromisoformat`.
- Parsing a compact/basic format → manual int slicing, never `fromisoformat`.
- Reaching for `strptime` → check whether the format is `fromisoformat`-safe on
  **3.10** first; the answer is usually yes for `isoformat()`-shaped input.

## Related

- `docs/specs/source-collector-contract.md` — the collector event contract, which
  now points here for the timezone policy.
- `.jules/bolt.md` — the measured performance history behind §4.
- `docs/specs/local-evidence-shadow-log.md`, `docs/specs/intent-capture.md` — the
  durable records §1 governs.
