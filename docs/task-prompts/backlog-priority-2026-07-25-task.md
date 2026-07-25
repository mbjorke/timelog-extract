# Backlog priority pass — 2026-07-25 (product owner)

Planning pass after the 2026-07-25 merge batch (#455, #459, #460, #461, plus #456).
No code changes: this is priority, acceptance criteria, and the decisions that must
be made before implementation.

**Second goal of this pass:** leave a set of **agent-ready bugs** — well-scoped,
already-decided, testable — so an implementing agent can start immediately without
waiting on a product decision.

## Traceability

- story_id: GH-462 (https://github.com/mbjorke/timelog-extract/issues/462)
- spec_status: approved
- implementation_status: not built
- created_at: 2026-07-25
- last_updated_at: 2026-07-25
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: this document (planning pass; no code)
- validation.decision: GO
- changelog:
  - 2026-07-25: Initial pass. Re-scoped GH-408 after partial delivery in #440;
    triaged #454; promoted three agent-ready bugs; recorded the 0.5 release framing.

## Context: where we actually are

- Version **0.3.1**. Target per the release thread: **0.5 within July** — six days
  left. That is the single biggest forcing function on this ordering.
- The 2026-07-23/25 batch (#447, #449, #450, #451, #452, #453, #455, #456, #459,
  #460, #461) cleared the review/onboarding and security lanes. The external-PR
  defense is now two code layers plus maintainer-applied GitHub settings
  (`docs/security/external-pr-hardening.md`).
- **Board drift confirmed again** (the recurring failure mode): the issue list is
  not a trustworthy view on its own — see the GH-408 finding below. Priorities in
  this pass were set by reading the code, not the labels.

## Finding: GH-408 is not done, and its spec says the wrong thing

`#408` sits at `priority:now`. PR **#440** shipped part of it, and the spec
`docs/task-prompts/commit-events-to-shadow-log-task.md` now claims
`implementation_status: built` with `validation.decision: GO` — while
`implementation.pr` is still `pending`.

Verified against the code:

| Scenario in GH-408 | State |
|---|---|
| 1. Commit recorded as a structured event in the shadow log | **built** (#440: hook capture, `git-commit` source alias) |
| 3. Ledger write failure is not silent | **built** (#440: try/except around the shadow-log write) |
| 2. Markdown worklog becomes a *view* generated from the ledger | **not built** — no function or CLI surface renders/append markdown from the ledger (`core/evidence_store.py` exposes replay/export/erase/prune only) |

This is the "ledger is the source of truth, markdown is a view" half of the
worklog-identity direction, and it is the part that is still missing.

**Action:** re-scope `#408` to scenario 2 only, and correct the spec's
Traceability (`implementation_status: in progress`, `implementation.pr: #440`).
Do not close `#408`.

---

# Ordered backlog

## now

### 1. GH-408 (re-scoped): markdown worklog becomes a view over the ledger

- priority: **now**
- problem: Commit events land in the shadow log (#440), but nothing renders a
  markdown worklog *from* the ledger. Until that exists, the ledger is a parallel
  store rather than the source of truth, and the markdown file stays authoritative
  by default.
- user value: One truth. The worklog file becomes reproducible output, so a lost or
  hand-edited `TIMELOG.md` is recoverable and never silently diverges from evidence.
- non-goals: Changing the hook (done). Changing the ledger format. Migrating
  historical markdown into the ledger. Removing markdown as a supported surface.
- behavior:

```gherkin
Scenario: Markdown worklog is generated from the ledger
  Given commit events exist in the shadow log
  When the user asks Gittan to render the project worklog
  Then the markdown is generated from the ledger records
  And the ledger remains the source of truth

Scenario: Rendering is idempotent and never destroys hand-written content
  Given a worklog file already contains hand-written entries
  When the worklog is rendered again from the ledger
  Then ledger-derived entries are appended or refreshed in place
  And hand-written content is preserved
```

- acceptance:
  - A documented surface renders a worklog view from ledger records.
  - Re-running produces no duplicate entries (idempotent).
  - Hand-written content in an existing worklog file survives a render.
  - Fixture tests cover: empty ledger, ledger with commits, re-render idempotency,
    and the preserve-hand-written case.
- validation: unit tests with a temp ledger + temp worklog file; inline
  `gittan` smoke on the new surface.
- dependencies: none blocking. **Open decision:** is the surface a new subcommand,
  a flag on an existing one, or part of `evidence`? Decide before implementation.
- **NEEDS_HUMAN**: writes a user worklog file (see `AGENTS.md` timelog file rules).
  Not an agent-auto-merge task.

### 2. GH-416: beta onboarding dry-run — first external tester end-to-end

- priority: **now** (unchanged)
- Non-code, and the only item here that cannot be parallelized or delegated to an
  agent. With a 0.5-in-July target, a real external run is what converts
  "it works on my machine" into a release signal.
- acceptance: one external person completes `gittan setup` + `doctor` + one real
  report on their own machine; the top friction items found are fixed.
- Keep as the human thread of the week.

### 3. GH-414: Chrome dashboard-work evaporation

- priority: **now** (unchanged)
- Accuracy-critical: sustained dashboard/SPA work disappears from reports
  (~180 raw visits collapsing to a handful, then absent downstream). This is the
  product's core promise — "find all the time" — failing on a real client block.
- Not agent-ready: two interacting mechanisms
  (`dedupe_web_visit_rows` / `thin_chrome_visit_rows_by_day` plus a downstream
  drop). Needs a measurement pass before a fix is designed.
- next step: reproduce with a fixture derived from the 2026-07-13 case and
  characterize each mechanism separately **before** changing thinning behavior.

### 4. GH-448: Lovable Desktop — open-app cache/storage ≠ authorship

- priority: **now** (unchanged)
- Trust-critical attribution semantics: ghost projects from merely having the app
  open. Related to the presence-vs-authorship taxonomy (#327).
- Not agent-ready: needs the product decision "what counts as authorship for a
  desktop app whose cache updates without the user acting?" before code.

---

## next (agent-ready bugs — see the section below)

- **GH-454** — Impact 0.0 on decidable Lovable rows is misleading *(promoted from
  untriaged; decision made below)*
- **GH-251** — Recalibrate the Screen Time evidence-gap warning *(promoted from
  `later`: acceptance criteria are already concrete and testable)*
- **GH-367** — Label provenance: mark enrichment-derived session labels as derived

Also staying at `next`, unchanged: #222, #254, #262, #264, #267, #272, #326, #327,
#332, #354, #368, #369, #406, #431.

---

## later / do not build yet

No changes this pass, except the two promotions above (#251 → `next`). The `later`
band (23 issues) is not re-litigated here; it is re-read when the 0.5 window closes.

---

# Agent-ready bugs (start immediately, no product decision pending)

These three are deliberately shaped so an implementing agent can pick one up
without asking a question first. Each has a **decided** rule, a small file surface,
and testable acceptance. Each is a genuine bug, not a refactor.

**Assignment discipline:** route these by assigning the issue or mentioning the
agent from a human comment. A bot-authored `@`-mention does not wake Jules
(`docs/runbooks/review-status-agent.md`), and a "success" report is not evidence —
**always check `git diff` / the PR files tab**, because an empty commit claiming
success has happened before.

## A. GH-454 — Impact 0.0 on decidable Lovable rows is misleading

- priority: **next**, agent-ready
- surface: `core/cli_review_create_project.py` (+ the review candidate ranking it
  feeds) — the same area as #449/#461, so the shape is familiar.
- problem: `gittan review` shows rows as **decidable** (human title, Events > 0,
  Days > 0) while **Impact = 0.0**. A row that looks worth mapping but claims zero
  impact teaches the user to distrust the column.
- **Product decision (made here, so it is not an open question):** a row is
  decidable **only if it carries a real report-hour signal**. Impact must never be
  presented as `0.0` on a decidable row. A row whose only evidence is presence or
  ambient noise belongs in **Park**, not in the decidable queue. Do **not** solve
  this by explaining the column in help text.
- behavior:

```gherkin
Scenario: A row with no report-hour signal is not decidable
  Given a review candidate whose impact hours round to 0.0
  And whose evidence is presence-only
  When the review candidate list is built
  Then the row is classified as undecidable
  And it is offered under Park, not under map/create

Scenario: A decidable row always shows a non-zero impact
  Given a review candidate presented in the decidable queue
  When the row is rendered
  Then its Impact value is greater than 0.0
```

- acceptance:
  - No decidable row can render `Impact 0.0`.
  - Presence-only rows land in Park with the existing Park copy.
  - Existing #449/#461 behavior (implausible UUIDs, unmapped-Lovable placeholders)
    still holds — those tests must stay green.
  - New tests cover: zero-impact + human title → undecidable; non-zero impact +
    human title → decidable; boundary at the rounding threshold.
- validation: `tests/test_cli_review_create_project.py` extended; inline
  `gittan review` smoke on a fixture config (never real client data).

## B. GH-251 — Recalibrate the Screen Time evidence-gap warning

- priority: **next** (promoted from `later`), agent-ready
- surface: the evidence-gap check + its spec
  `docs/task-prompts/evidence-gap-recalibration-task.md`.
- problem: The gap warning treats expected non-work screen time as missing
  evidence, so a healthy report gets flagged. A warning that cries wolf trains the
  user to ignore it — worse than no warning.
- why it is agent-ready: the spec already carries concrete, numeric Gherkin
  (a 30-day report with 110h observed vs 149h Screen Time must **not** be flagged),
  which is exactly the kind of acceptance criteria an agent can implement against.
- acceptance:
  - The documented healthy case (110h / 149h over 30 days) produces no warning.
  - A genuinely low-coverage case still warns.
  - The threshold is expressed as coverage ratio, not raw hour difference, and is
    documented where the warning is produced.
  - Tests cover: healthy month, low-coverage month, and the threshold boundary.
- validation: unit tests over the gap check with synthetic totals; no real Screen
  Time data in fixtures.

## C. GH-367 — Label provenance: mark enrichment-derived session labels as derived

- priority: **next** (unchanged), agent-ready
- surface: `core/worklog_enrich.py::enrich_delivery_session_labels`, the timeline
  renderer, and the JSON payload.
- problem: Cross-source enrichment paints delivery rows (commits, GitHub activity)
  with the nearest prior AI session title on a 2-hour lookback. In the timeline a
  painted row is visually **indistinguishable** from a row whose own source produced
  the label — the invisibility behind the July 9–10 incident family (#351, #361).
- scope note: this task is **provenance only** — make derived labels visible as
  derived. Changing *which* label wins is #369 and is explicitly out of scope here.
- behavior:

```gherkin
Scenario: A painted label is visibly marked as derived
  Given a delivery row whose session label came from cross-source enrichment
  When the timeline is rendered
  Then the label is marked as derived rather than shown as the row's own label

Scenario: Derived provenance is machine-readable
  Given a delivery row whose session label came from enrichment
  When the JSON payload is produced
  Then the row carries an explicit derived-label provenance field
```

- acceptance:
  - Terminal timeline distinguishes derived labels from source-produced labels,
    following `docs/product/terminal-style-guide.md` (no new rainbow coloring).
  - JSON payload carries an explicit provenance field for derived labels.
  - A row whose own source produced the label is **not** marked derived.
  - Tests cover both directions (derived and not-derived).
- validation: unit tests on the enrichment path + a payload assertion.
- dependency: the JSON shape is the extension boundary — if the field lands in the
  truth payload, check `TRUTH_PAYLOAD_VERSION` handling in `core/truth_payload.py`.

---

## Decisions needed from the maintainer

1. **GH-408 surface** — new subcommand, flag, or part of `evidence`? Blocks the
   `now` item.
2. **GitHub settings for the external-PR defense** — the two maintainer-only
   toggles in `docs/security/external-pr-hardening.md` (fork-run approval; required
   review on `main`). Code layers are shipped; these are not.
3. **Cursor automations** — `review-status` and `Jules finisher` are UI-only and
   still route work to `@jules`, which does not wake from a bot mention. Until
   routing is human-only they add churn to every PR (both were re-triggered by a
   push during this session).

## Non-goals for this pass

- No code changes.
- No re-litigation of the 23-issue `later` band.
- No new sources or collectors.
- No change to the review-lens or merge-gate policy (settled in #437/#441/#445).
