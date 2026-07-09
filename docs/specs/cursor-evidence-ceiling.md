# Cursor evidence ceiling

Status: draft spec  
Last updated: 2026-06-15

## Purpose

Document what honest, local-first evidence Gittan can extract from Cursor on
macOS — and what it cannot. This caps collector design so we do not fabricate
per-turn chat timing or chase Claude Desktop–style cache patterns that do not
exist for Cursor.

Validated on maintainer machine (Cursor 3.7.x, 2026-06-11 / 2026-06-15). Paths
below use `~` for the user home directory.

## Summary

| Question | Answer |
| --- | --- |
| Per-message / per-turn wall-clock locally? | **No** first-class store suitable for billing-grade evidence. |
| Cached conversation/events API like Claude Desktop? | **No** — Chromium cache holds update checks, not turn timelines. |
| Honest Cursor timing ceiling for Gittan today? | **`composer.composerHeaders`** in global `state.vscdb`, emitted as bounded burst heartbeats (`collectors/cursor_composer.py`). |
| Plain Cursor IDE logs? | Timestamped but overwhelmingly IDE background noise (~96% on a validated test-heavy day); weak project attribution. |

When evidenced Cursor hours badly under-represent a full working day, the
product response is a **separate presence-estimated band** — not reconstructing
fake per-turn events. See `docs/task-prompts/presence-estimated-hours-task.md`.

## What Gittan uses today

### Composer headers (primary)

**Path:** `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`  
**Key:** `composer.composerHeaders` → JSON `allComposers[]`

Each composer (agent thread) exposes **session-level** metadata only:

- `createdAt`, `lastUpdatedAt`, `conversationCheckpointLastUpdatedAt`
- `workspaceIdentifier` / `agentLocation` (repo path for classification)
- `trackedGitRepos[].branches[].lastInteractionAt` (sparse branch touches)
- `name` (human title — label anchor)

There are **no** per-bubble or per-turn timestamps in this payload.
`bubbleId`, `checkpointId`, and `agentKv` references appear in transport/logs
as identifiers without wall-clock fields attached.

Collector: `collectors/cursor_composer.py` — merges in-window touches into
14-minute bursts; does **not** grid-fill idle gaps between `createdAt` and
`lastUpdatedAt` across days.

### Cursor checkpoints (secondary, sparse)

**Path:** `~/Library/Application Support/Cursor/User/globalStorage/anysphere.cursor-commits/checkpoints/*/metadata.json`

Single `startTrackingDateUnixMilliseconds` per checkpoint plus file paths /
`workspaceId`. Useful as occasional direct-work anchors, not a dense timeline.

### Cursor IDE logs (tertiary, filtered)

**Path:** `~/Library/Application Support/Cursor/logs/**/*.log`

Line timestamps exist, but most lines are extension host, git pollers, MCP,
marketplace, and filesystem churn. `collectors/cursor.py` applies aggressive
noise filters (`strict` / `ultra-strict`) and requires a workspace path in the
line. Not suitable as chat-turn timing.

## Local stores that are *not* collector-grade

### Legacy chat blob DB (`~/.cursor/chats`)

**Path:** `~/.cursor/chats/<hash>/<composerId>/store.db`

SQLite tables `blobs(id, data)` and `meta`. Message bodies are JSON blobs
(`role`, `content`) **without per-blob timestamps**. Thread `meta` may include
`createdAt` and `name` only at conversation level.

On the validated machine this tree contained only stale threads (April 2026);
active composer data lives in `state.vscdb` headers, not here. Treat as legacy /
abandoned storage path unless Cursor revives it with per-turn times.

### Agent transcripts (`~/.cursor/projects/.../agent-transcripts`)

**Path:** `~/.cursor/projects/<workspace-slug>/agent-transcripts/<id>.jsonl`

One JSON object per line: `role` + `message`. **No timestamp field** in the JSON.
Order implies sequence, not wall time. Useful for debugging exports, not
honest hour reconstruction.

### AI code tracking (`~/.cursor/ai-tracking/ai-code-tracking.db`)

Per-code-hash `createdAt` tied to `conversationId` / `composer` source — commit
and attribution telemetry, not a chat turn log. Wrong evidence class for session
duration.

### Chromium disk cache

**Path:** `~/Library/Application Support/Cursor/Cache/Cache_Data`

Unlike Claude Desktop (see below), scanned entries are predominantly
`api2.cursor.sh/updates/...` — no cached
`/sessions/.../events` (or equivalent) response bodies with per-event
`created_at`.

Per `docs/ideas/til/2026-06.md`: cache-reading is a **last resort** for
Electron apps whose primary timeline is server-side (Claude Desktop, Lovable
Desktop). Cursor is an IDE fork with structured local state; scraping its cache
is out of policy even if a future build started caching conversation APIs.

## Comparison: Claude Desktop events cache (what Cursor lacks)

Claude Desktop Code sessions are reconstructable from:

```
~/Library/Application Support/Claude/Cache/Cache_Data
  key: https://claude.ai/v1/sessions/<id>/events?...
  body: zstd → JSON { data: [{ created_at, type, cwd, ... }, ...] }
```

Spec: `docs/task-prompts/claude-desktop-chat-code-evidence.md`  
Collector: `collectors/claude_desktop_events.py`

Cursor conversations stream over the agent transport (`kvClientMessage`,
`conversationCheckpointUpdate`, `agentKv`) to server-side KV. That stream is
**not** persisted locally as a dense, timestamped event list Gittan can mine with
the same collector pattern.

## Footnote: structured logs / hooks (per-turn time, weak evidence)

### Always-local (Cursor ≤ 3.9.x)

**Path:** `~/Library/Application Support/Cursor/logs/.../anysphere.cursor-always-local/Cursor Structured Logs*.log`

JSON lines include:

- `agent.turn.start` / `agent.turn.outcome` with **log-line wall time**
- `metadata.conversation_id` — same UUID as `composerId` in
  `composer.composerHeaders` (joinable for title/workspace via headers)
- `workspaceId` often appears in the **log file name**, not in every event

### Hooks channel (Cursor 3.10+)

**Path:** `~/Library/Application Support/Cursor/logs/.../output_*/cursor.hooks.workspaceId-*.log`

Validated on maintainer machine after upgrade to **Cursor 3.10.20** (2026-07-09,
GH-345): always-local logs no longer emit `agent.turn.start` (last seen
2026-07-04 on client 3.9.16). Turn-ish wall-clock moved to hooks payloads:

- `hook_event_name: beforeSubmitPrompt` with `conversation_id` / `session_id`
  (same UUID as `composerId`), `workspace_roots`, optional `transcript_path`
- Timestamp from the preceding `[ISO-8601]` log line (UTC), not from the JSON body
- `preToolUse` / `postToolUse` are denser and must **not** be treated as turns

Collector: `collectors/cursor_agent_turns.py` unions always-local + hooks, then
dedupes by `conversation_id` so multi-window hook copies do not double-count.

This remains **log-based evidence**:

- rotation and retention match ordinary IDE logs, not durable audit storage;
- attribution requires joins (conversation_id → composer header → workspace);
- source role is still `direct_work_evidence` via log scrape — fragile and
  policy-discouraged for IDE forks, but the only honest per-turn local signal.

## Implications for product and collectors

1. **Do not** add a Claude Desktop–style cache collector for Cursor unless a
   future Cursor build caches timestamped conversation APIs locally (verify with
   cache key scan, not assumptions).
2. **Do not** grid-fill composer `createdAt`→`lastUpdatedAt` spans across idle
   time — that fabricates hours (validated: full-span → ~14.6h vs ~5.5h
   evidenced on a test-heavy day).
3. **Do** keep composer burst-per-touch as the honest Cursor timing ceiling with
   project attribution.
4. **Do** treat Screen Time as a **coverage comparator** for under-evidenced
   days (`docs/specs/source-evidence-policy.md`), via a labeled
   presence-estimated display field — never mixed into observed/billable totals.
5. **Shadow log** (`docs/specs/local-evidence-shadow-log.md`) could retain
   normalized composer-header touches before `state.vscdb` compaction; it cannot
   invent per-turn data that upstream never stored.

## Related

- Collector implementation: `collectors/cursor_composer.py`, `collectors/cursor.py`
- Presence-estimated band (downstream product): `docs/task-prompts/presence-estimated-hours-task.md`
- Source roles: `docs/specs/source-evidence-policy.md`
- Claude Desktop counterexample: `docs/task-prompts/claude-desktop-chat-code-evidence.md`
- Composer burst fix context: `docs/task-prompts/repo-time-totals-task.md`

## Validation notes

- 2026-06-11: test-heavy Cursor day — ~407k log lines, ~96% filtered as noise;
  evidenced ~5.54h vs composer full-span fabrication ~14.6h vs Screen Time
  ~15.1h.
- 2026-06-15: `conversation_id` in structured logs matched `composerId` in
  headers; `~/.cursor/chats` contained two stale `store.db` files only;
  Chromium cache had no session/events keys.
