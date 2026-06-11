# Mapping & signals — how we build forward (June 2026)

Status: active roadmap  
Last updated: 2026-06-11  
Owner: Maintainer

**Purpose:** One place to resume after [#139](https://github.com/mbjorke/timelog-extract/pull/139)
(calendar) merged and while [#140](https://github.com/mbjorke/timelog-extract/pull/140)
(mapping anchors) is open. Separates **ship-ready** work from **draft specs**
that landed in the same branch but are not built yet.

## The arc in one paragraph

The old **Freelance Bridge** hosted-dashboard idea is retired
(`docs/ideas/conversational-ui-stack.md`). The replacement is **private-first**:
stronger local classification signals, audit-driven config suggestions, and
light modal-wall nudges in the CLI — then intent capture and triage UX once weak
web/chat signals can be tagged at source. Calendar onboarding (Pierre) and IDE/terminal
mapping (Marcus-style power users) are **parallel tracks** on the same engine.

---

## What is on `main` today

| Area | Shipped | Pointer |
| --- | --- | --- |
| Calendar collector + roles | P1 | `collectors/calendar.py`, `--calendar-source on` |
| Weekly pivot | P2 | `gittan report --weekly` |
| Title-code classification | P3 | `match_terms` + calendar titles |
| Zero-export onboarding | P4 | `docs/runbooks/calendar-time-report-onboarding.md` |
| Project codes from history | P7 | `gittan calendar-suggest` |

**Not on main yet:** activity anchors, `top_signals`, anchor nudges — all in PR #140.

**Calendar still open (P5–P8):** corroboration, gap nudges, invoice last mile —
see `docs/product/calendar-beat-the-parser-backlog.md`; blocked on
`scheduled-reported-time-bridge` for P5+.

---

## PR #140 — merge scope vs baggage

Treat #140 as **one shippable feature** plus **planning docs**. Do not block merge
waiting for intent capture or triage UI.

### Merge-ready (code + tests)

| Deliverable | Spec / evidence |
| --- | --- |
| `anchors` map on events (`dir` / `branch` / `label`) | `docs/specs/working-directory-anchor-signal.md` |
| `context_dir` on Cursor, Windsurf, Antigravity, Gemini CLI | collector tests |
| `projects-audit` → `top_signals` (schema v2) | `core/projects_audit.py` |
| `--write-anchor-plan` + `projects-anchor` (match_terms + tracked_urls) | `test_projects_audit.py` |
| `status` / `report` anchor nudges (anchors only; hosts → `review`) | `core/anchor_nudge.py`, `test_anchor_nudge.py` |

Branch execution log (slice #1 details): `docs/ideas/freelance-bridge-planning-arc.md`.

### Docs-only in #140 — **not implemented** (do not read as shipped)

| Doc | Status | Next action |
| --- | --- | --- |
| `docs/specs/intent-capture.md` | draft spec | New PR: JSONL write path + classification consumer |
| `docs/ideas/triage-design-session-learnings.md` | paused UX | Restart **after** intent capture MVP |
| `docs/ideas/triage-signal-examples.md` | grounding (Document A) | Keep for design sessions; not a build ticket |
| `docs/ideas/conversational-ui-stack.md` | exploratory | Policy when picking UI surface per decision weight |
| `docs/decisions/private-not-local.md` | decision | Reference when choosing `~/.gittan/` storage |
| `docs/ideas/hermes-agent-distribution.md` | idea | Optional external agent runtime |

---

## Recommended build order after #140 merges

Pick **one row = one PR** (`task/<scope>` from `main`). Re-sync `main` before each.

### Track A — Config hygiene (extends anchor work; no new product surface)

| Order | Slice | Why now | Suggested branch |
| --- | --- | --- | --- |
| A1 | **Haystack from `anchors + detail`** | Stops collector/classify drift while anchors are fresh | `task/classify-haystack-from-anchors` |
| A2 | **Unified plan executor** (`op ∈ {add, remove}`) | One reviewed JSON for trim + anchor instead of two commands | `task/projects-plan-executor` |
| A3 | **Nudge registry** | Thresholds/copy for anchor, uncategorized, screen-time in one module | `task/nudge-registry` |
| A4 | `label` beyond Codex (Claude history, web titles) | More `top_signals` coverage | `task/anchor-label-sources` |
| A5 | Rename `--max-top-hosts` → `--max-top-signals` | Naming honesty; optional breaking change | `task/rename-max-top-signals` |

### Track B — Intent capture (fixes weak web/chat signals)

| Order | Slice | Exit criteria |
| --- | --- | --- |
| B1 | Append-only `~/.gittan/intent-capture.jsonl` + `gittan intent tag` | Gherkin in `intent-capture.md` scenarios 1–2 |
| B2 | `classify_project` consumes intent by `url_hash` | Scenario 3 + provenance field |
| B3 | Restart triage UX design (5-prompt session) | Preconditions in `triage-design-session-learnings.md` met |

### Track C — Calendar leapfrog (Pierre P5–P8)

Depends on `scheduled-reported-time-bridge` reconcile loop. Sequence: **P5 corroboration
→ P6 gap nudges → P8 invoice**. Do not mix with Track A unless touching shared
report surfaces — coordinate in one PR if so.

### Track D — Medium UI (deferred)

React Ink overlay for anchor mapping; SQLite for triage/intent index; web view for
`gittan review` at high decision weight. See `conversational-ui-stack.md`.

---

## How to choose the next PR

```
Need Pierre/calendar trust layer?     → Track C (after bridge spec work)
IDE/terminal mapping still painful?   → Track A (A1 haystack first)
claude.ai / opaque URLs the blocker?  → Track B (intent capture)
Want prettier mapping UX?             → Track D (after A1–A3 stabilize contracts)
```

**Default after #140:** **A1** (haystack) — small, testable, reduces silent misclassification.

---

## Operator smoke (after #140 on main)

```bash
gittan projects-audit --from YYYY-MM-DD --to YYYY-MM-DD --json | jq '.schema_version, .top_signals[:3]'
gittan status    # one-line anchor warning when thresholds hit
gittan report …  # multi-line anchor nudge at end
```

Playbook: `docs/ideas/fast-project-mapping-playbook.md`.

---

## Agent handoff checklist

1. Read **this file** + `docs/specs/implementation-status.md`.
2. Confirm `main` has #139 and #140 merged; `git fetch origin main`.
3. Create `task/<scope>` from latest `main` — do not extend the old `claude/freelance-*` branch name.
4. If the task touches collectors, read `docs/specs/source-collector-contract.md`.
5. Update `implementation-status.md` when a spec crosses `built` / `verified`.
6. Append a short note to `docs/ideas/til/YYYY-MM.md` when the maintainer corrects priority or scope.

## Related

- `../ideas/freelance-bridge-planning-arc.md` — #140 branch execution log
- `../product/calendar-beat-the-parser-backlog.md` — Pierre P1–P8
- `../ideas/fast-project-mapping-playbook.md` — ~10 min config tuning loop
- `../specs/working-directory-anchor-signal.md` — anchor + audit contract
- `../specs/intent-capture.md` — next root fix for triage pain
