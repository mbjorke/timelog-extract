# Reported/approved time layer — phased backlog

## Context

`gittan jira-sync` / `toggl-sync` and the invoice deliverable read **observed**
time directly and push/bill from it. The evidence policy says no source should
silently promote observed time to pushed/billed. The missing **Reported time**
layer (between classified and approved) is the foundation. The bridge spec
([`../specs/scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md))
designed the `reported_time` record (states `proposed`/`confirmed`/`edited`/
`dismissed`); this task-prompt slices the build into phases and tracks status.

**Amendment (invoice lens):** gittan systematically UNDERCOUNTS — it can't see
SFTP, mail, phone/in-person meetings, or other machines (ÅSS mars: 18.75h billed
vs ~3.0h observed). Observed is the **floor, not the ceiling**, so the layer must
let the user **add net-new manual time** with no observed origin. Implemented as
`source="manual"` with nullable `origin_ref` but a **required note** (never a
silent fabrication). This relaxes the bridge spec's "no orphan reported time"
rule for explicitly user-authored manual entries.

## Decisions (locked with maintainer)

- **D1 Storage:** new JSONL store, one record per line, **monthly global** files
  at `~/.gittan/reported/YYYY-MM.jsonl` (mirrors `core/evidence_store.py`).
- **D2 Granularity:** `project + day` (matches jira/toggl sync + the invoice
  deliverable); per-event provenance kept in `origin_ref`.
- **D3 Manual-add provenance:** a user `note` is required for orphan
  (`source: manual`) records.
- **D4 Adoption / fallback:** when reported_time exists for a window, sync/invoice
  read **only `confirmed`/`edited`**; when none exists, fall back to today's
  observed behavior (opt-in, nothing breaks before adoption).
- **D5 Truth payload:** emit `confirmed` reported_time at a `TRUTH_PAYLOAD_VERSION`
  bump so the extension / invoice / feed read one source. *(Phase 4/5.)*

## Phased backlog

### Phase 1 — `reported_time` record + local store
- priority: **built** — PR #186 (merged)
- scope: `core/reported_time.py` — `ReportedTimeRecord` + append-only event-sourced
  JSONL store, deterministic ids (latest write per id wins), graceful loads, and
  `reported_hours_by_project_day()` (confirmed/edited only). `source="manual"`
  requires a note and rejects `origin_ref`; non-manual requires `origin_ref`.
- acceptance: write→read round-trip; query by project+day+state; manual-needs-note
  / non-manual-needs-origin validation; aggregation excludes proposed/dismissed.
- validation: `tests/test_reported_time.py`; full suite green.

### Phase 2 — reconcile / confirm / add CLI
- priority: **in review** — PR #187 (stacked on #186, retargeted to main)
- scope: `gittan reported` group — `review` (confirm/edit/dismiss observed
  proposals per project+day; dry-run writes nothing; already-reported skipped),
  `add` (manual net-new time; note required, hours>0), `list` (confirmed totals).
  `core/reported_sync.py::build_reported_proposals` aggregates observed sessions
  into proposals.
- acceptance: confirm→`confirmed`; edit→`edited`+`edited_from_hours`; dismiss→
  `dismissed`; add→`manual` with note; dry-run no write; already-reported skip.
- validation: `tests/test_cli_reported.py`; full suite green.

### Phase 2b — auto-reporting (`gittan reported sync`)
- priority: **built** — this PR
- scope: most observed time should auto-confirm into the reported store for
  well-configured projects, so manual review shrinks to the exceptions and the
  agent surface stays quiet. Policy-safe via an **explicit per-project opt-in**
  `auto_report: true` (the user pre-authorizes — not a silent promotion, per
  `source-evidence-policy.md`). `core/reported_sync.py::split_auto_confirm`
  marks eligible proposals (configured project, opted in, not `Uncategorized`) as
  `confirmed`; `gittan reported sync` writes them non-interactively and leaves the
  rest for `reported review`. `auto_report` added to `normalize_profile`.
- acceptance: opted-in project's observed time → `confirmed` written; non-opted →
  nothing written (stays unreported); `Uncategorized` never auto-confirms;
  `--dry-run` writes nothing; already-reported project+days skipped.
- validation: `tests/test_reported_sync.py`, `tests/test_cli_reported.py`.
- non-goals (refinement, later): gate on dominant source strength (exclude
  passive-only sessions) per the evidence policy's roles.

### Phase 3 — sync reads `confirmed`
- priority: **next** — not built
- scope: `build_toggl_entry_candidates` / `build_jira_worklog_candidates` source
  from `confirmed`/`edited` reported_time (project+day) instead of raw observed
  sessions, with the D4 fallback. Closes the evidence-policy gap (no silent
  observed→pushed).
- behavior:
  ```gherkin
  Scenario: Sync posts confirmed reported time, not raw observed
    Given confirmed reported_time exists for Project Alpha on a day
    When the user runs toggl-sync / jira-sync for that window
    Then the candidate uses the confirmed hours (incl. manual additions)

  Scenario: Fallback before adoption
    Given no reported_time exists for the window
    Then sync uses today's observed behavior unchanged
  ```
- acceptance: with confirmed records, sync posts those numbers; with none, observed
  behavior unchanged; tests.
- dependencies: Phase 1–2.

### Phase 4 — invoice reads the same layer
- priority: **later** — not built
- scope: `/gittan-invoice` reads confirmed reported_time (incl. manual-added) so
  email + Briox line + Excel use the single source; the "Billable" column fills
  from confirmed × `--billable-unit`.
- dependencies: Phase 1–2; D5.

### Phase 5 — Lovable feed GUI (review/approve surface)
- priority: **later** — not built
- scope: the feed renders proposed→confirm/edit/dismiss/add over the truth-payload
  reported_time; web equivalent of the Phase 2 CLI.
- dependencies: Phase 1–2; D5.

### Parallel — Calendar collector (bridge-spec phase 2)
- priority: **later** — not built (independent source feeder)
- scope: read opted-in calendars with role-per-calendar; time-report calendar →
  `confirmed` primary_claim, meetings → `proposed`. Built via
  `/gittan-source-collector`. Slots in after Phase 2.

## Verification approach

Per phase: unit tests on the store + CLI (fixtures, never live data); the existing
jira/toggl live-test pattern for Phase 3 (confirmed → push). Full suite green; no
Python file over 500 lines.

## Traceability

- story_id: GH-TBD (reported/approved time layer)
- spec_status: draft
- implementation_status: in progress — Phase 1 built (#186), Phase 2 built (#187),
  Phase 2b (auto-reporting) built (this PR); Phases 3–5 + Calendar not built
- created_at: 2026-06-25
- last_updated_at: 2026-06-25
- implementation.pr: #186 (merged), #187 (merged), + this PR (Phase 2b)
- implementation.branch: task/reported-time-record, task/reported-confirm-cli,
  task/reported-auto-report
- implementation.commits: []
- validation.evidence: `tests/test_reported_time.py`, `tests/test_cli_reported.py`;
  full suite green (1001)
- validation.decision: GO for Phase 1–2; Phases 3–5 pending
- related:
  - design root: [`../specs/scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md)
  - policy: [`../specs/source-evidence-policy.md`](../specs/source-evidence-policy.md)
  - invoice reality: gittan undercount (see Context)
- changelog:
  - 2026-06-25: Backfilled from a local plan-mode file into a committed task-prompt
    after Phases 1–2 had already shipped (#186/#187) without a traceable spec —
    the exact gap the product-owner skill update now prevents. Locked decisions
    D1–D5 and the manual-add amendment recorded; Phases 3–5 + Calendar named.
  - 2026-06-25: Phase 2b (auto-reporting) built — `auto_report` per-project opt-in
    + `gittan reported sync`; observed time for well-configured projects
    auto-confirms (policy-safe via explicit opt-in). Surfaced by the
    "gittan in the agent" vision (statusline shows the remaining exceptions).
