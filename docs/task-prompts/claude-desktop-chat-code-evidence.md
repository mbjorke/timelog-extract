# Claude Desktop: Code / Chat session evidence from the cached events API

## Problem

Claude Desktop has three activity modes — **Chat**, **Cowork**, **Code** — but
the current `collect_claude_desktop` path only surfaces Cowork log rows. Code
and Chat sessions leave no timeline evidence, so a multi-hour Claude Desktop
Code session can produce **zero observed hours** even though it did real work.

Earlier candidate sources turned out to be single-point or empty:

- session-metadata JSON (`claude-code-sessions/**/local_*.json`): one
  `lastFocusedAt`, often a stale `lastActivityAt`.
- `session-diff-stats-store` (Local Storage): one cumulative `updatedAt`
  snapshot, not a duration.
- per-turn CLI logs (`~/.claude/projects/**`): for the validated day, only two
  `pr-link` rows (filtered as noise) — no real turns.

## Validated evidence source (primary)

Claude Desktop caches the **session events API** response locally, in the
Chromium disk cache, **zstd-compressed**:

```
key:  https://claude.ai/v1/sessions/<session-id>/events?limit=500&after_id=...
body: zstd → JSON {"data": [ {created_at, type, message, uuid, session_id}, ... ],
                   "has_more", "first_id", "last_id"}
```

Location: `~/Library/Application Support/Claude/Cache/Cache_Data/*_0`
(Chromium "simple cache" entries: 20-byte header, key, then the response
stream; body is zstd, magic `28 b5 2f fd`; an EOF record marks stream end).

`type` ∈ {`user`, `assistant`, `system`, `env_manager_log`, `control_request`,
`control_response`, `result`, `rate_limit_event`, `tool_progress`}. Each event
has a real `created_at` ISO timestamp; events also carry `cwd`/`owner/repo`
which gives per-event project attribution.

Validated reconstruction (one session, one day): ~2,360 events, 1,057
`user`/`assistant` turns, clustered (15-min idle gap) into one ~2.6h active span
plus short touches — matching the user's recollection and the
`git-worktrees`/diff-stats signals for the same session id. The session id is
exactly the value behind Claude Desktop's **"Copy link"**
(`https://claude.ai/code/session_<id>`), so it is user-verifiable.

### Privacy (mandatory)

`message.content` contains the **full chat/code text** (and signature blobs).
The collector must read **only** `created_at`, `type`, `session_id`, and the
`cwd`/`owner/repo` attribution fields. Never persist or surface message content.

### Retention caveat

The cache evicts oldest entries (same as Lovable `Cache_Data`): recent sessions
reconstruct reliably; sessions from days/weeks ago may be gone. Git commits on
`claude/<branch>` remain the durable long-range fallback.

## Shared Electron-cache reader (build once, reuse)

Claude Desktop and Lovable Desktop both use the Chromium "simple cache" with
compressed HTTP bodies (Claude=zstd, Lovable=brotli). Factor the common parsing
into one helper — e.g. `core/chromium_cache.py`:

- `iter_cache_entries(cache_dir, key_substr)` → yields `(key, mtime, body_bytes)`
  after parsing the simple-cache header and decoding brotli/zstd.
- codecs imported lazily; missing codec → helper yields nothing (no crash).

Each collector then only supplies its URL path (`/v1/sessions/.../events` here,
Lovable's project paths there) and its field extraction. See
`docs/task-prompts/lovable-cache-evidence.md`, which shares this reader.

## Task

1. New `collectors/claude_desktop_events.py` (keep `ai_logs.py` under 500 lines):
   - enumerate `Cache_Data/*_0` entries whose key contains
     `/v1/sessions/` and `/events`,
   - parse the simple-cache header, locate the zstd frame, decompress
     (`zstandard`; add as a dependency), `json.loads` the body,
   - collect `data[]` events, dedupe by `uuid`, keep only `created_at` in the
     report window,
   - emit one event per **active cluster** (15-min idle gap) so session hours
     are honest, attributed via `cwd`/`owner/repo` (reuse the repo-slug helper
     from `repo-slug-project-attribution.md` when available),
   - detail: `Code session <session-prefix> — N turns` (no message text).
2. Performance: cap scanned bytes per run; skip entries > a few MB pre-decompress
   guard; never crash on unreadable/binary/evicted entries.
3. Source naming: surface as `Claude Desktop` (mode `[code]`), or a dedicated
   sub-source — decide with maintainer (affects `core/sources.py`, evidence
   legend, `AI_SOURCES`). Chat-mode events from the same cache can be added the
   same way and cross-checked 1:1 against Claude.ai (web)/Chrome (dedupe so a
   conversation is not double-counted).
4. `gittan doctor`: report Claude Desktop events cache availability (mirror the
   Lovable storage-signals doctor row so doctor never contradicts the report).
5. Fixture tests: synthetic simple-cache entry with a zstd `/events` body using
   neutral placeholders (`project-alpha`, `owner/repo`, `session_<id>`); assert
   (a) cluster→hours, (b) no message content leaks into detail, (c) evicted/
   corrupt entry is skipped without error.

## Acceptance criteria

- A Claude Desktop Code session reconstructs honest active hours from the cached
  `/events` body, attributed to the correct project.
- Message content never appears in any event detail or persisted artifact.
- Evicted/old sessions degrade gracefully (no crash, no fabricated hours).
- `gittan doctor` reflects events-cache availability.
- Full autotest suite green; no Python file exceeds 500 lines.

## Non-goals

- No keystroke capture, no network MITM, no fetching from claude.ai — local
  cache only (consistent with `lovable-cache-evidence.md` Non-goals).
- Not storing or rendering chat/code message text.

## Traceability

- story_id: GH-142
- spec_status: approved
- implementation_status: verified
- created_at: 2026-06-11
- last_updated_at: 2026-06-12
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/141
- implementation.branch: task/claude-desktop-events
- implementation.commits: [5c76a70]
- validation.evidence: PR #140 thread (2026-06-11/12); zstd-decompressed cached /v1/sessions/<id>/events reconstructed ~2.6h active across 1,057 turns for the session behind Claude Desktop "Copy link"; cross-checked vs git-worktrees + diff-stats
- validation.decision: GO
- changelog:
  - 2026-06-11: Initial draft (IndexedDB / diff-stats sources).
  - 2026-06-12: Rewritten around the validated primary source — zstd-compressed
    cached `/v1/sessions/<id>/events` responses (full turn log with timestamps +
    repo attribution). Demoted session-JSON/diff-stats/CLI-log to weaker
    fallbacks. Added mandatory privacy (timestamps/type only, no message text),
    retention caveat, doctor row, and zstandard dependency note.
  - 2026-06-12: Implemented on `task/claude-desktop-events` — shared
    `core/chromium_cache.py` reader + `collectors/claude_desktop_events.py`
    (source `Claude Desktop (Code)`), doctor row, `cache-evidence` optional
    extra, fixture tests. Real-data smoke: the validated session reconstructs
    06:51→09:28+ attributed to the correct project.
  - 2026-06-12: Merged via PR #141; maintainer validated real-data output
    (single titled session, honest span, no background-ping hours). Story
    GH-142 closed; status verified / GO.
