# Lovable Desktop: cache-mtime evidence for full-day session reconstruction

## Backlog (product-owner)

Ordered slice after Claude Desktop Code (#141 / GH-142) and repo-slug attribution
(#144 / GH-143). Spec: this file. Story: **GH-145**.

### Lovable cache-mtime + project titles

- **priority:** `now`
- **problem:** Morning Lovable sessions vanish because LevelDB storage signals
  only keep each file's final write; the report shows at most one late-day touch.
- **user value:** Honest hours and **invoice-readable project titles** (not bare
  UUID prefixes) for Lovable Desktop work that never touched History DB.
- **non-goals:** No keystroke capture, no network MITM, no chat text from disk
  (see below). Cache is a last-resort source — not a replacement for git/TIMELOG
  when those exist.
- **dependencies:** `core/chromium_cache.py` (merged #141); optional
  `timelog-extract[cache-evidence]` for brotli; existing
  `_LOVABLE_PROJECT_UUID_RE` + RudderStack filter in `lovable_desktop.py`.
- **acceptance:** See Behavior Contract + Acceptance Criteria below.
- **validation:** Re-run the 2026-06-11 window: cache mtimes 09:32–09:53 (and
  git-bot commits 09:38–09:47) appear in `gittan report` with human project
  title in detail; RudderStack UUIDs absent; `bash scripts/run_autotests.sh`
  green.

### Later (same Electron-cache family)

- **priority:** `later`
- **Claude Desktop Chat events** from cached session list (dedupe vs
  Claude.ai/web/Chrome) — spec slice not yet written.
- **priority:** `later`
- **`gittan doctor` parity** for all cache-backed sources (Claude events cache ✓;
  Lovable cache row when this ships).

## Problem

Lovable Desktop has no Chromium `History` database, so the collector falls back
to storage signals (`Local Storage`/`Session Storage`/`IndexedDB` LevelDB
blobs). Those blobs only retain the **latest write per file**: a morning work
session is overwritten by compaction later in the day, so the timeline shows at
most one event per file at the file's final mtime.

Validated gap (2026-06-11): a Lovable session on `project-alpha` produced
git commits via Lovable's GitHub bot (`gpt-engineer-app[bot]`) between
09:38–09:47 local, but the report showed no Lovable event before 18:45.

## Validated evidence source

`~/Library/Application Support/lovable-desktop/Cache/Cache_Data/*` (and
`Code Cache/js/*`) entries keep their **per-request mtimes all day** and
contain the Lovable project UUID in request URLs and analytics beacons, e.g.:

```
url=https://lovable.dev/projects/<uuid>&tiba=<Project Title> - Lovable
```

On the validation day, cache files containing the project UUID reconstructed
work sessions 09:32–09:53, 10:11, 10:38–10:40, 11:41, 12:12, 13:03–13:14 —
matching the git-bot commit window.

## Non-goals (decided 2026-06-11)

- **No keystroke capture.** A per-app keylogger (macOS Accessibility / CGEventTap)
  could in theory be scoped to a single app, but it would be a new source class
  with per-app complexity and — more importantly — it breaks Gittan's
  local-first, trustworthy-evidence promise. Not pursued.
- **No network MITM.** Reading the outgoing POST body to `api.lovable.dev` to
  recover the user's typed sentences is equally out of scope.
- **Chat text is server-only.** A raw byte scan of the entire `lovable-desktop`
  data dir (LevelDB, IndexedDB, Session Storage, Cache) found **none** of the
  user's typed sentences. The only chat-looking local string was a
  *predefined suggestion button* label baked into the app's `Code Cache` JS, not
  user input. Conclusion: the user's posted messages never touch local disk;
  there is no local "outbox" to read. Gittan does not need chat text for its job
  (hours + project attribution) — git commits from `gpt-engineer-app[bot]` are
  the content layer when content is wanted.

## Bonus local source: `projects/search` (UUID → human title)

The cached response of
`GET https://api.lovable.dev/workspaces/<ws>/projects/search` decompresses
(brotli) to the user's full project list with names and activity counters, e.g.:

```json
{"id": "<project-uuid>", "display_name": "Project Alpha",
 "last_edited_at": "<iso-ts>", "edit_count": 19, "edits_24h": 4}
```

This lets the collector map `unmapped Lovable (<uuid-prefix>…)` → the real
project title **with zero manual `gittan map` rounds for UUIDs**, and
`edit_count` / `edits_24h` give per-project session intensity. Prefer this over
the `tiba=` beacon when present.

## Shared Electron-cache reader (build once, reuse)

Lovable Desktop and Claude Desktop both use the Chromium "simple cache" with
compressed HTTP bodies (Lovable=brotli, Claude=zstd). Use the shared helper
`core/chromium_cache.py` (`iter_cache_entries`, `read_cache_entry`, lazy
codecs, missing codec = skip entry). This collector supplies Lovable URL paths
and field extraction; Claude Desktop (Code) already uses the same reader (merged
#141). **Do not fork** a second cache parser per app.

## Behavior Contract

Evidence role: **direct_work_evidence** (same class as existing Lovable storage
signals — local traces that justify observed hours when History DB is absent).
Privacy: project UUID, mtime, and **metadata titles only** (`display_name`,
`tiba=` beacon). Never persist or surface chat message text from cache bodies.

```gherkin
Feature: Lovable Desktop cache evidence for full-day sessions
  Recover honest timeline hours from Chromium cache mtimes when LevelDB storage
  signals were overwritten, with invoice-readable project titles.

  Background:
    Given Lovable Desktop has no History database
    And the collector already reads storage signals as a fallback
    And core/chromium_cache.py is available with brotli when cache-evidence extra is installed

  Scenario: Morning session visible from cache mtimes when storage was overwritten
    Given cache files under lovable-desktop Cache/Cache_Data contain a project UUID
    And those files have mtimes between 09:32 and 09:53 local on the report day
    And LevelDB storage signals for the same UUID only show a late-day write at 18:45
    When gittan report runs for that day
    Then Lovable (desktop) events appear at the cache mtime timestamps
    And the session is not limited to the single late storage-signal touch

  Scenario: Human project title in report detail for invoice review
    Given a cached projects/search response maps the UUID to display_name "Project Alpha"
    When gittan report includes a cache-evidence event for that UUID
    Then the event detail shows "Project Alpha" (or the mapped project name)
    And the detail is not only "unmapped Lovable (<uuid-prefix>…)"

  Scenario: Unknown UUID keeps the existing map nudge format
    Given a cache file references a Lovable UUID with no profile mapping
    And projects/search has no title for that UUID
    When gittan report runs
    Then the event detail uses the unmapped Lovable (uuid…) — map UUID via gittan map format
    And the event project is Uncategorized

  Scenario: RudderStack analytics UUID never fabricates a project
    Given a cache entry contains a UUID only inside RudderStack analytics context
    When the Lovable collector scans cache files
    Then no event is emitted for that UUID

  Scenario: Missing brotli codec degrades gracefully
    Given brotli is not installed
    And cache mtimes still identify activity for a known UUID
    When gittan report runs
    Then cache-mtime events may still appear from raw cache key/beacon scans
    And gittan doctor explains cache-evidence optional extra when projects/search bodies cannot be decoded
    And the collector never crashes

  Scenario: Corrupt or oversized cache entry is skipped silently
    Given a cache file is truncated binary garbage or exceeds the size guard
    When the Lovable collector scans cache files
    Then no error is raised
    And other valid cache entries in the same run still produce events
```

### Test mapping

| Scenario | Evidence (planned) |
| --- | --- |
| Morning session from cache mtimes | `tests/test_lovable_desktop.py` fixture: in-window cache file + late-only storage signal |
| Human project title | fixture: synthetic brotli `projects/search` body via `chromium_cache` |
| Unknown UUID nudge | fixture: unmapped uuid, no search title |
| RudderStack skip | existing + extended `_is_analytics_uuid_context` cache scan test |
| Missing brotli | mock/import skip; doctor row assertion |
| Corrupt/oversized skip | fixture junk `_0` entry |

## Task

1. Add a cache-evidence path to `collectors/lovable_desktop.py`:
   - scan `Cache_Data` (and `Code Cache/js`) files with mtime inside the
     report window,
   - search file bytes for Lovable project UUIDs (reuse
     `_LOVABLE_PROJECT_UUID_RE`; respect the analytics-context filter so
     RudderStack queue ids never fabricate projects),
   - emit one event per (uuid, mtime-burst), merged with the existing
     `_merge_storage_events` collapse logic.
2. Prefer UUIDs already known from `match_terms`/`tracked_urls`; unknown UUIDs
   keep the `unmapped Lovable (…) — map UUID via gittan map` detail format.
3. Performance guard: skip files larger than a few MB; cap total scanned bytes
   per run; never crash on unreadable/binary content.
4. Resolve UUID → human project title from the cached `projects/search`
   response (brotli body; `id` → `display_name`); fall back to the
   `tiba=<title>` beacon. Title is stronger mapping evidence than the bare UUID.
5. Fixture tests: synthetic cache dir with (a) known-uuid file in window,
   (b) rudder-context uuid file (must be skipped), (c) out-of-window file,
   (d) brotli `projects/search` title map, (e) corrupt/oversized entry skipped.
6. `gittan doctor`: extend the Lovable row when cache evidence is readable
   (mirror Claude Desktop (Code) events-cache row pattern).

## Acceptance criteria

- A Lovable work session that only left cache traces (no storage-blob tail
  write) appears in `gittan report` for that window with the right timestamps.
- Report details show **human project titles** when `projects/search` or
  `tiba=` provides them (invoice-readable, not UUID-only).
- RudderStack/telemetry UUIDs never appear as projects.
- Evicted/corrupt/oversized cache entries degrade gracefully (no crash).
- `gittan doctor` reflects Lovable cache readability when applicable.
- Full autotest suite green; no Python file exceeds 500 lines.

## Traceability

- story_id: GH-145
- spec_status: approved
- implementation_status: built
- created_at: 2026-06-11
- last_updated_at: 2026-06-15
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/148
- implementation.branch: task/lovable-cache-evidence
- implementation.commits: [f3031a8, c1fa8d6, 914a182, 84e6747, 9bd6b5f]
- validation.evidence: PR #148; autotests 793 green; live 2026-06-11 Lovable title + landsbanken mapping; composer span bounded vs Screen Time
- validation.decision: conditional GO
- changelog:
  - 2026-06-11: Initial draft created from live validation-day investigation.
  - 2026-06-11: Added Non-goals (no keystroke/MITM capture; chat text is
    server-only, confirmed by raw byte scan) and `projects/search` UUID→title
    bonus source. doctor now reports Lovable as collecting via storage signals.
  - 2026-06-12: Product-owner pass — backlog (`now`), Behavior Contract
    (Gherkin), test mapping table, doctor row task, traceability GH-145;
    clarified reuse of merged `core/chromium_cache.py` (#141).
  - 2026-06-15: Implementation on task/lovable-cache-evidence; PR #148 opened.
