# Lovable Desktop: cache-mtime evidence for full-day session reconstruction

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
{"id": "8e18db4d-…", "display_name": "Ålandsbanken FAQ Helper",
 "last_edited_at": "2026-06-11T06:47:28Z", "edit_count": 19, "edits_24h": 4}
```

This lets the collector map `unmapped Lovable (8e18db4d…)` → the real project
title **with zero manual `gittan map` rounds for UUIDs**, and `edit_count` /
`edits_24h` give per-project session intensity. Prefer this over the `tiba=`
beacon when present.

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
   (b) rudder-context uuid file (must be skipped), (c) out-of-window file.

## Acceptance criteria

- A Lovable work session that only left cache traces (no storage-blob tail
  write) appears in `gittan report` for that window with the right timestamps.
- RudderStack/telemetry UUIDs never appear as projects.
- Full autotest suite green; no Python file exceeds 500 lines.

## Traceability

- story_id: GH-pending
- spec_status: draft
- implementation_status: not built
- created_at: 2026-06-11
- last_updated_at: 2026-06-11
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: investigation in PR #140 thread (2026-06-11); cache-mtime reconstruction matched gpt-engineer-app[bot] commit window 09:38–09:47
- validation.decision: NO-GO
- changelog:
  - 2026-06-11: Initial draft created from live validation-day investigation.
  - 2026-06-11: Added Non-goals (no keystroke/MITM capture; chat text is
    server-only, confirmed by raw byte scan) and `projects/search` UUID→title
    bonus source. doctor now reports Lovable as collecting via storage signals.
