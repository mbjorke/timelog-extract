# Freelance Bridge planning arc — execution log and roadmap

Status: active branch work (`claude/freelance-bridge-dashboard-CeFO5`, 2026-06)  
Last updated: 2026-06-11

## Context

The **Freelance Bridge** dashboard prototype is retired as a product shape
(see `conversational-ui-stack.md`). This branch carries the **private-first**
replacement: stronger local signals, audit-driven rule suggestions, modal-wall
nudges, and planning docs for intent capture and triage UX — not a hosted
middleware dashboard.

Use this file as the **agent handoff** when resuming the branch: what landed,
what was intentionally *not* unified yet, and the recommended next slices.

## Completed slices

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
applies **both** rule types (`apply_rule_to_project` already supported
`tracked_urls`; the apply loader was relaxed from match_terms-only).

**Audit JSON:** `schema_version: 2`; payload key is `top_signals` only (no
stale `top_hosts` / `top_anchors` keys). Internal helpers
`aggregate_top_hosts` / `aggregate_top_anchors` remain as per-kind backends
for `aggregate_signal` — intentional.

### Boundary held on purpose (#1)

**`status` / `report` nudges stay anchor-only** (`dir` / `branch` / `label`).
They call `unanchored_top_anchors`, not `unanchored_top_signals`.

**`gittan review` keeps interactive host → project mapping.** Batch host
suggestions live in audit + `--write-anchor-plan` + `projects-anchor`; the
modal-wall nudge does not compete with review for hosts.

Uncategorized / screen-time nudges still point at `gittan review` for URL
hosts.

## Recommended next slices (not built)

Order from the 2026-06-11 design session — adjust if product priority shifts.

| # | Slice | Rationale |
| --- | --- | --- |
| **4** | Derive classification **haystack** from `anchors + detail` in one place | Cheap correctness win while the anchor model is fresh; reduces drift between what collectors prepend and what `classify_project` sees |
| **2** | Merge `projects-trim` + `projects-anchor` into one **plan executor** (`op ∈ {add, remove}`) | One reviewed JSON plan for rule hygiene instead of parallel trim/anchor commands |
| **3** | **Nudge registry** | Centralise threshold/copy/surface routing for report/status nudges (anchors, uncategorized, screen-time, …) |

Other follow-ups already on the anchor spec: `label` coverage beyond Codex;
React Ink overlay for medium-weight mapping; intent capture (`specs/intent-capture.md`).

## Verification notes (#1)

- Full gate: `bash scripts/run_autotests.sh` (643 tests at time of merge).
- Live smoke: `gittan projects-audit --json` → `schema_version: 2`, `top_signals`
  rows with `rule_type`; human table includes a **Rule** column; mixed plans
  tag `anchor_kind` + `rule_type` (host rows appear when browser activity exists
  in the window).

## Related

- `../specs/working-directory-anchor-signal.md` — normative anchor + audit contract
- `conversational-ui-stack.md` — modal wall; why review owns high-weight host mapping
- `fast-project-mapping-playbook.md` — operator workflow using `top_signals`
- `triage-design-session-learnings.md` — paused triage UX; needs intent capture
- `../specs/intent-capture.md` — next root fix for weak web/chat signals
