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
4. The `tiba=<title>` beacon can resolve UUID → human project title; if cheap,
   surface it in the event detail (title is stronger mapping evidence than the
   bare UUID).
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
