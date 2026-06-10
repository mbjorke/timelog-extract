# Triage grounding — real signal examples (Document A)

Status: reference (grounding document for triage UX design session restart)

Last updated: 2026-06-10

## Purpose

This document is **Document A** from `triage-design-session-learnings.md`. It shows what the classifier actually sees, source by source, on a real workday. Any designer (human or AI) inventing triage UX from scratch will imagine richer signals than exist here. Embed this in Prompt 0 before running the five-prompt Claude.ai design session.

Identifiers are anonymized per AGENTS.md fixture hygiene. Mapping used:

| Real name (local only)     | Placeholder used here |
|----------------------------|-----------------------|
| `project-alpha`            | `project-alpha`       |
| real project B             | `project-beta`        |
| real project C             | `project-gamma`       |
| real project D             | `project-delta`       |
| real OSS/CLI project       | `project-oss`         |
| real finance client repo   | `project-finance`     |
| real client name           | `client-a`            |
| `/Users/<maintainer>/`     | `/Users/developer/`   |
| GitHub handle              | `developer`           |

---

## Signal quality by source

### 1. Claude Code CLI — near-zero signal

The majority of Claude Code CLI events have a single-word detail:

```json
{
  "source": "claude_code_cli",
  "detail": "log",
  "timestamp": "2026-06-10T08:14:32",
  "project": "project-alpha",
  "confidence": 0.0
}
```

Occasionally a short snippet of truncated agent reasoning appears (~60 chars):

```json
{
  "source": "claude_code_cli",
  "detail": "Now let me check the existing test structure to understand",
  "timestamp": "2026-06-10T09:03:11",
  "project": "project-alpha",
  "confidence": 0.0
}
```

**Classifier view:** Cannot infer project from text alone. Attribution comes entirely from adjacency to other same-session events (Cursor/Chrome/GitHub events pointing at the same project). Without adjacency, these events become genuinely unclassifiable opaque time blocks.

---

### 2. Cursor — high frequency, all truncated

Cursor emits 50–80+ events per second during active editing. Every event is a filesystem or git log line truncated to ~90 characters:

```json
{
  "source": "cursor",
  "detail": ".git — 2026-06-02 19:15:25.504 [info] > git --git-dir /Users/developer/Workspace/project-alpha/.gi",
  "timestamp": "2026-06-02T19:15:25",
  "project": "project-alpha",
  "confidence": 0.6
}
```

```json
{
  "source": "cursor",
  "detail": "src/api.ts — 2026-06-02 19:15:27.001 [info] TypeScript language server initializing",
  "timestamp": "2026-06-02T19:15:27",
  "project": "project-alpha",
  "confidence": 0.6
}
```

```json
{
  "source": "cursor",
  "detail": ".git — 2026-06-03 14:44:12.882 [info] > git --git-dir /Users/developer/Workspace/project-gamma/.gi",
  "timestamp": "2026-06-03T14:44:12",
  "project": "project-gamma",
  "confidence": 0.6
}
```

**Classifier view:** Path fragment (`project-alpha/.gi`, `project-gamma/.gi`) is the only signal. The content of the truncated line is irrelevant. When a project's folder name matches a `match_terms` entry, Cursor events classify correctly at medium confidence. When the folder name differs from any `match_terms` entry, every Cursor event is unclassified.

---

### 3. Claude.ai (web) — partial thread titles, often good signal

Thread titles are truncated to ~40 characters. When the title contains project-relevant words, classification works. When the thread is opaque (early in a conversation, no memorable title set), it is genuinely unknowable.

Good signal example (title contains semantic content):
```json
{
  "source": "claude.ai",
  "detail": "chat/c369ea29-647f… — AI-driven kundservice för client-a -",
  "timestamp": "2026-06-10T10:22:07",
  "project": "project-beta",
  "confidence": 0.7
}
```

Opaque example (UUID + short truncation):
```json
{
  "source": "claude.ai",
  "detail": "chat/a81f3c00-2b1e… — How do I configure the",
  "timestamp": "2026-06-10T11:44:55",
  "project": null,
  "confidence": 0.0
}
```

Long-lived planning thread (classified by URL match via `tracked_urls`):
```json
{
  "source": "claude.ai",
  "detail": "chat/d44b8e71-9a3c… — project-oss architecture planning",
  "timestamp": "2026-06-10T13:05:44",
  "project": "project-oss",
  "confidence": 0.85
}
```

**Classifier view:** Two classification paths exist. (1) `match_terms` against the visible ~40-char title fragment. (2) `tracked_urls` where the user has explicitly mapped the chat UUID to a project. Without one of these, the event is unclassifiable regardless of triage effort — the title text is all the classifier ever sees.

---

### 4. Chrome — richest source, full page titles

Chrome emits full page titles, making it the most signal-dense source when the user's browser is active:

```json
{
  "source": "chrome",
  "detail": "feat(calendar): suggest projects from calendar titles (P7) by developer · Pull Request #139 · developer/timelog-extract",
  "timestamp": "2026-06-10T09:17:33",
  "project": "project-oss",
  "confidence": 0.95
}
```

```json
{
  "source": "chrome",
  "detail": "project-gamma / app / src / components / InvoiceForm.tsx at main · developer/project-gamma",
  "timestamp": "2026-06-03T15:02:11",
  "project": "project-gamma",
  "confidence": 0.8
}
```

```json
{
  "source": "chrome",
  "detail": "Untitled document - Google Docs",
  "timestamp": "2026-06-02T16:45:00",
  "project": null,
  "confidence": 0.0
}
```

**Classifier view:** GitHub repo names and PR titles classify strongly. Generic SaaS pages (Google Docs, email, Slack threads without subject visible) do not classify. Chrome is the most reliable source for confidence > 0.8 events.

---

### 5. GitHub — structured, reliable signal

GitHub events are formatted strings rather than page titles:

```json
{
  "source": "github",
  "detail": "created branch task/calendar-suggest-projects in developer/timelog-extract",
  "timestamp": "2026-06-10T08:55:22",
  "project": "project-oss",
  "confidence": 0.9
}
```

```json
{
  "source": "github",
  "detail": "pushed 3 commits to task/fix-cursor-dedup in developer/timelog-extract",
  "timestamp": "2026-06-10T17:33:01",
  "project": "project-oss",
  "confidence": 0.9
}
```

**Classifier view:** Repo name in the detail string almost always maps directly to a `match_terms` entry. GitHub events are consistently high confidence when the project is configured. The signal gap: GitHub only sees push/PR/branch events — it cannot account for time spent reading code without committing.

---

### 6. TIMELOG.md — commit messages, strong signal

Manual worklog entries and commit messages are the most deliberate signals:

```json
{
  "source": "TIMELOG.md",
  "detail": "- Commit: fix(ci): stabilize nightly Security Scans in project-oss",
  "timestamp": "2026-06-10T18:10:00",
  "project": "project-oss",
  "confidence": 1.0
}
```

```json
{
  "source": "TIMELOG.md",
  "detail": "- Manual: client-a sync call 45min",
  "timestamp": "2026-06-03T10:00:00",
  "project": "project-beta",
  "confidence": 1.0
}
```

**Classifier view:** Always confidence 1.0 when a match exists. These are the ground truth events; everything else is inference.

---

### 7. Lovable (desktop) — opaque UUID, no text signal

Lovable desktop sessions emit a storage signal containing a project UUID:

```json
{
  "source": "lovable",
  "detail": "storage signal — https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/",
  "timestamp": "2026-06-02T20:30:15",
  "project": null,
  "confidence": 0.0
}
```

With a `tracked_urls` entry mapping the UUID to a project:

```json
{
  "source": "lovable",
  "detail": "storage signal — https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/",
  "timestamp": "2026-06-02T20:30:15",
  "project": "project-gamma",
  "confidence": 0.85
}
```

**Classifier view:** Binary. Either the UUID is in `tracked_urls` (classified, medium-high confidence) or it is not (unclassifiable by any amount of triage effort). The only fix is URL mapping at setup time or via intent capture at the moment of work.

---

## Confidence spectrum in practice

| Confidence band | What it means in practice | Example sources |
|-----------------|---------------------------|-----------------|
| `1.0`           | Manually entered or commit-anchored | TIMELOG.md entries |
| `0.85–0.95`     | Strong title match or explicit `tracked_urls` hit | Chrome PR page, GitHub branch event, Claude.ai thread with project name in title |
| `0.6–0.84`      | Path fragment match or partial term match | Cursor (folder name match), Chrome (repo browse), Claude.ai (ambiguous title) |
| `0.0–0.59`      | No text signal; adjacency or fallback only | Claude Code CLI `log` events, Lovable UUID without mapping |
| `null / unset`  | Genuinely unclassifiable by the engine | Claude.ai opaque threads, Chrome generic tabs, Lovable unmapped UUID |

---

## What this means for triage UX

1. **Most events the user will see in triage have `confidence < 0.6` or `null`**. The common case is not "confirm this looks right" — it is "the engine has no idea what this is."

2. **The unclassifiable events fall into two camps:**
   - *Inferrable with context*: A 45-minute Claude Code CLI block adjacent to Cursor events for `project-alpha` → user confirms "yes, that was project-alpha." One decision classifies the whole block.
   - *Genuinely unknowable*: A Lovable UUID never mapped, or a Claude.ai thread whose title is `"How do I configure the"`. No amount of UI can help here; the fix is intent capture *before* the session ends.

3. **Session-level triage is the right granularity**, not individual events. A 2-hour session with 120 Cursor events all from the same path fragment should show as one triage decision, not 120 rows.

4. **The design must show adjacent high-confidence events** as context for low-confidence ones. A `confidence: 0.0` Claude Code CLI block sitting between two `confidence: 0.9` GitHub events for the same project is far easier to classify than the same block shown in isolation.

5. **First-run case**: 200 unclassified events with no project config yet. The triage UX must handle this as a distinct flow (bootstrap → create first project → classify against it), not just a long review queue.

---

## Related

- `../specs/intent-capture.md` — addresses the genuinely-unknowable camp at the source
- `../ideas/triage-design-session-learnings.md` — why the previous design session failed and the five-prompt structure to reuse
- `../ideas/fast-project-mapping-playbook.md` — the manual workflow triage must improve on
- `../product/cli-command-map.md` — full command inventory including `review --json` output contract
