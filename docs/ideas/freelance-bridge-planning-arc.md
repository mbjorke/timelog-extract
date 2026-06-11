# Freelance Bridge planning arc — PR #140 execution log

Status: branch log for [#140](https://github.com/mbjorke/timelog-extract/pull/140)  
Last updated: 2026-06-11

> **How to build forward after merge:** see the canonical roadmap
> [`../roadmaps/mapping-signals-continuation-2026-06.md`](../roadmaps/mapping-signals-continuation-2026-06.md)
> (tracks, PR order, draft-vs-built split). This file keeps the #140 slice detail.

## Context

The **Freelance Bridge** dashboard prototype is retired as a product shape
(see `conversational-ui-stack.md`). PR #140 ships the **private-first**
mapping slice: activity anchors, unified `top_signals` audit, and modal-wall
nudges — plus draft docs for intent capture and triage UX (not built in #140).

## Completed in #140

| # | Slice | Status | Evidence |
| --- | --- | --- | --- |
| — | Multi-kind **activity anchors** on events (`dir` / `branch` / `label`) | built | `docs/specs/working-directory-anchor-signal.md`; collectors + `core/events.py` |
| — | `context_dir` extended to Cursor, Windsurf, Antigravity, Gemini CLI | built | collector tests |
| — | Auto-surface unmapped anchors in `status` / `report` | built | `core/anchor_nudge.py`, `core/report_nudges.py` |
| **1** | Unify `top_hosts` + `top_anchors` → **`top_signals`** | built | commit `38aac8d`; `core/projects_audit.py` |

### What #1 changed

`top_hosts` and `top_anchors` are now **one `top_signals` model** — one audit
path instead of two parallel ones:

| Before | After |
| --- | --- |
| `top_hosts` (host, hits, anchored) | `top_signals` row: `{kind: host, rule_type: tracked_urls, …}` |
| `top_anchors` (kind, value, hits, anchored) | `top_signals` row: `{kind: dir/branch/label, rule_type: match_terms, …}` |

**One aggregation path:** `aggregate_signal` / `is_signal_anchored` /
`build_top_signals` dispatch per kind instead of two hand-coded tracks.

**One suggestion/plan path:** `projects-audit --write-anchor-plan` tags each
addition with the correct `rule_type` (hosts → `tracked_urls`); `projects-anchor`
applies **both** rule types.

### Boundary held on purpose (#1)

**`status` / `report` nudges stay anchor-only** (`dir` / `branch` / `label`).
**`gittan review` keeps interactive host → project mapping.**

## Next slices (after #140 — see roadmap for order)

| # | Slice | Track |
| --- | --- | --- |
| **4** | Haystack from `anchors + detail` | A — config hygiene |
| **2** | Unified trim/anchor plan executor | A |
| **3** | Nudge registry | A |
| — | Intent capture MVP | B |
| — | Triage UX restart | B (after intent) |

Full table and branch naming: `../roadmaps/mapping-signals-continuation-2026-06.md`.

## Verification (#140)

- `bash scripts/run_autotests.sh`
- `gittan projects-audit --json` → `schema_version: 2`, `top_signals`
