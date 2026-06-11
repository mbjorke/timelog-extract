# Claude Desktop: separate Chat / Cowork / Code evidence

## Problem

Claude Desktop has three distinct activity modes — **Chat**, **Cowork**, and
**Code** — but the current `collect_claude_desktop` path only surfaces Cowork
log rows. Chat and Code sessions leave no timeline evidence, so e.g. a
~1h Claude Desktop Code session produces zero observed hours even though the
work resulted in git commits on a `claude/...` branch.

## Validated local evidence (2026-06-11)

All three modes leave local traces under
`~/Library/Application Support/Claude/`:

1. **Chat** — IndexedDB (`IndexedDB/https_claude.ai_0.indexeddb.blob/...`)
   contains chat records with conversation UUID, human title, model, and
   ISO timestamp. Validated: a chat record (`<conversation-uuid>`, a project
   title, `<iso-ts>`) matched the corresponding Claude.ai (web) Chrome-history
   event at the same wall-clock minute — Chat events can be
   **cross-checked against Claude.ai (web)/Chrome** rows (dedupe required:
   same conversation should not double-count).
2. **Code** — two stores:
   - `Local Storage/leveldb/*.ldb` key `session-diff-stats-store` (origin
     `https://claude.ai`): per-session diff stats keyed by
     `<session>:<owner>/<repo>:<branch>` with additions/deletions/fileCount
     and `updatedAt` epoch-ms. Validated: a `claude/<branch>` entry with
     non-zero additions across several files.
   - IndexedDB session records: title, environment id (`env_…`), repo URL
     (`https://github.com/<owner>/<repo>`), `refs/heads/<branch>`, and
     created/updated timestamps.
3. **Cowork** — already collected today (keep as-is).

## Task

1. Extend `collectors/ai_logs.py` (or a new `collectors/claude_desktop.py`
   under the 500-line limit) with:
   - **Chat events**: parse IndexedDB blob records (regex-over-bytes is
     acceptable, same approach as Lovable storage) → conversation UUID,
     title, timestamp. Detail: `<title> — chat/<uuid-prefix>`.
   - **Code events**: parse `session-diff-stats-store` and IndexedDB session
     records → repo, branch, updatedAt. Detail:
     `<repo>@<branch> — +<additions>/-<deletions> (<fileCount> files)`.
     Project classification gets repo+branch in the haystack, so
     `match_terms` like `owner/repo` attribute directly.
2. Source naming: keep `Claude Desktop` as the source, but prefix detail with
   the mode (`[chat]`, `[code]`, `[cowork]`) OR introduce sub-sources — decide
   with maintainer before implementation (affects `core/sources.py`,
   evidence legend, and `AI_SOURCES`).
3. Dedupe: a Chat conversation also visible as Claude.ai (web)/Chrome rows
   must not double-count session time (existing collapse/dedupe in
   aggregation may already cover this — verify with a fixture).
4. Fixture tests for both stores (synthetic LevelDB/IndexedDB byte blobs);
   never hardcode real customer/project names — use `project-alpha` style
   placeholders.

## Acceptance criteria

- A Claude Desktop Code session with commits on a `claude/...` branch shows up
  as observed time attributed to the right project.
- Chat sessions appear once (no double-count with web evidence).
- Cowork behavior unchanged.
- Full autotest suite green; 500-line limit respected.

## Traceability

- story_id: GH-pending
- spec_status: draft
- implementation_status: not built
- created_at: 2026-06-11
- last_updated_at: 2026-06-11
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: investigation in PR #140 thread (2026-06-11); IndexedDB chat record matched a Claude.ai (web) event at the same minute; session-diff-stats-store matched claude/ branch work
- validation.decision: NO-GO
- changelog:
  - 2026-06-11: Initial draft created from live validation-day investigation.
