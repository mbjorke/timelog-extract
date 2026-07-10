# Blind-spot pass — 2026-07-10 (product-owner)

Product-owner planning pass that turns the six *unknown-unknowns* surfaced by a
"blind spot pass" over the codebase into an ordered, behavior-ready backlog. No
code is changed here — this is the prioritization and the acceptance criteria
behind it.

**Technique:** map-vs-territory blind-spot pass (Thariq Shihipar, *A Field Guide
to Fable: Finding Your Unknowns*). The *map* is our policy docs (`CLAUDE.md`,
`AGENTS.md`, the collector/evidence contracts); the *territory* is what the code
actually does. Each item below is a place the territory has quietly drifted from
the map — the class of gap that no single PR and no green CI run would flag.

**Decision filter (from `docs/product/gittan-vision.md`):** does the next
`gittan report` / invoice show the operator the *right* hours for their
acceptance window? Trust and local-first are non-negotiable; agent activity must
never silently become billable, and — the framing this pass adds — **hours we
never collected, or silently misattributed, are the most dangerous kind of wrong
because they are invisible.** Priority follows how directly an item protects that
invoice-trust surface.

## Traceability

- story_id: `pending` (issues created on approval via `/docs-to-issues`; see Issue plan)
- spec_status: `draft`
- implementation_status: `not built` (planning artifact — no code)
- created_at: `2026-07-10`
- last_updated_at: `2026-07-10`
- implementation.pr: pending
- implementation.branch: `claude/codebase-unknowns-el498z`
- implementation.commits: []
- validation.evidence: this backlog + issue label state after the pass
- validation.decision: `GO` (as a planning deliverable)
- changelog:
  - `2026-07-10: Initial blind-spot pass; six findings ordered now/next/later.`

## How the findings map to priority

| # | Finding | Touches invoice trust? | Priority |
| - | ------- | ---------------------- | -------- |
| 1 | Collectors swallow errors → silently missing billable hours | Directly (invisible under-count) | **now** |
| 2 | Session merge may cross project boundaries → misattributed hours | Directly (if broken, wrong invoice) | **now** (spike first) |
| 3 | Consent/retention contract applied unevenly across collectors | Yes (local-first / privacy is non-negotiable) | **next** |
| 4 | Four collectors have no dedicated tests (two are core sources) | Indirectly (untested counting path) | **next** |
| 5 | 500-line rule is gamed to 499, not "split by responsibility" | No (maintainability) | **later** |
| 6 | `TRUTH_PAYLOAD_VERSION` frozen at "1", no migration path | No (extension compat debt) | **later** |

---

## now

### Collector silent-failure becomes a visible doctor signal

- priority: now
- problem: Collectors use broad swallow-and-continue error handling
  (`collectors/chrome.py:139`, `:189`; `collectors/mail.py:104`, `:127`; ~39
  `except Exception` and ~13 `except … pass` across `collectors/`). When a
  collector partially fails — a locked SQLite DB, a moved log path, a permission
  change after an OS update — the report gets *quieter* with no signal. For a
  tool whose entire promise is "trust these hours for the invoice," the most
  dangerous number is the one we failed to collect, and today it is invisible.
- user value: A degraded source announces itself instead of silently shrinking
  the invoice. The operator can tell "this was a light week" apart from "Chrome
  history was locked and we saw nothing."
- non-goals:
  - Do not change session or billing math.
  - Do not make a collector error abort the whole run — degrade, don't crash.
  - Do not attempt to *recover* the lost data in this slice; only surface it.
- behavior:

```gherkin
Feature: A degraded collector is visible, never silent
  A collector that fails or partially fails is reported in doctor/source-summary,
  so a shrunk report is never mistaken for a light week.

  Scenario: A collector raises mid-run
    Given the Chrome history database is locked during a report run
    When the pipeline collects events
    Then the run completes with the other sources' events
    And the Chrome source is reported with a degraded collector_status and reason
    And "gittan doctor" surfaces the degraded source with its error class

  Scenario: A healthy run reports no degraded sources
    Given every enabled collector returns without error
    When the report runs
    Then no source is marked degraded
```

- acceptance:
  - Broad `except Exception` sites in collectors either narrow to the expected
    error classes or record a structured degraded status (source, reason,
    error class) instead of swallowing to `pass`.
  - `collector_status` in the truth payload distinguishes `ok` /
    `empty` / `degraded`; `gittan doctor` and `--source-summary` render degraded
    sources distinctly.
  - A collector exception never aborts the whole report.
- validation: unit test that injects a raising collector and asserts (a) the run
  completes, (b) the source is marked degraded with a reason, (c) doctor shows
  it. Manual: `gittan doctor` against a machine with one source path removed.
- dependencies: touches `core/pipeline.py`, `core/collector_registry.py`,
  `core/truth_payload.py` (`collector_status`), and the doctor/source-summary
  renderers. Align the status vocabulary with `docs/sources/sources-and-flags.md`.

### Spike: does session attribution respect project boundaries?

- priority: now (spike/verify first; fix only if the assumption is broken)
- problem: `core/domain.py::compute_sessions` (`:176`) merges events whose gaps
  are under `gap_minutes` into one session purely by timestamp, and
  `session_duration_hours` measures `end - start` of that merged span. This is
  correct **only if** events are already grouped per project before
  `compute_sessions` is called. If two projects' events interleave within the
  15-minute window anywhere upstream, their time collapses into one session and
  hours leak between projects — the worst category under the decision filter
  (a wrong invoice), and one that looks perfectly plausible in the output.
- user value: Confidence that per-project hours are actually per-project, or a
  named bug if they are not.
- non-goals:
  - Do not refactor the session model pre-emptively — first establish whether
    the boundary is respected on the real aggregation path
    (`core/report_aggregate.py::aggregate_report`).
  - Do not change billing rounding (`billable_total_hours` is correct).
- behavior:

```gherkin
Feature: Sessions never merge across projects
  Time is attributed to the project that produced it, even when two projects'
  events are close together in wall-clock time.

  Scenario: Interleaved two-project activity
    Given project A and project B each have events at 10:00, 10:05 and 10:10
    When sessions and hours are computed for the report
    Then project A's hours derive only from project A's events
    And project B's hours derive only from project B's events
    And no minute is counted toward both
```

- acceptance:
  - A test exercises interleaved multi-project events end-to-end through
    `aggregate_report` and asserts hours do not leak across projects.
  - If the spike finds a leak, this item splits into a fix item (promoted to
    `now`) with the failing case as its regression test; if not, the spike
    closes with the test as a guard and a one-line note in the spec.
- validation: the new end-to-end test is the evidence. Record GO/NO-GO on
  whether a leak exists.
- dependencies: `core/domain.py`, `core/report_aggregate.py`, `core/analytics.py`.

---

## next

### Audit consent/retention coverage across all collectors

- priority: next
- problem: The source-collector contract (`docs/specs/source-evidence-policy.md`,
  the `gittan-source-collector` skill) requires each source to declare consent /
  `collector_status` / retention posture, but only four collectors
  (`calendar`, `conductor`, `git_commits`, `vscode_fork`) reference those terms
  today, out of ~24. For a local-first, privacy-first tool this uneven
  application is a real trust gap — but it is *unknown* whether the other
  collectors are genuinely non-compliant or simply passive-context sources that
  inherit a default. The audit is the deliverable; it converts an unknown into a
  known list.
- user value: A defensible answer to "what does Gittan read, under what consent,
  and how long does it keep it?" — per source, not per vibe.
- non-goals:
  - Do not add new data sources.
  - Do not change what is collected; only make the posture explicit and
    consistent.
- behavior:

```gherkin
Feature: Every collector declares its evidence and consent posture
  No source reads local data without a declared role, consent basis, and
  retention expectation.

  Scenario: Auditing an existing collector
    Given a registered collector
    When the source-evidence audit runs
    Then the collector declares an evidence role from the policy table
    And it declares whether it requires opt-in consent
    And any collector missing a declaration is listed as a gap
```

- acceptance: a table (source → evidence role → consent basis → retention/
  fragility note) covering every registered collector, with each gap either
  closed or explicitly justified (e.g. "passive context, inherits default").
- validation: the completed table reviewed against `source-evidence-policy.md`;
  optionally a `--check` that fails when a registered collector has no declared
  role (mirrors the feature-inventory gate).
- dependencies: `core/sources.py`, `core/collector_registry.py`, every
  `collectors/*.py`.

### Test coverage for the four untested collectors

- priority: next
- problem: `collectors/git_commits.py`, `collectors/ai_logs.py`,
  `collectors/cursor_log_scan.py`, and `collectors/vscode_fork.py` have no
  dedicated test file. `git_commits` and `ai_logs` feed reported hours directly,
  so a parsing regression there is a silent miscount — the collector contract
  calls for fixture tests, and the map and territory disagree here.
- user value: Changes to these collectors get caught by CI instead of by a wrong
  invoice.
- non-goals: do not rewrite the collectors; add characterization/fixture tests
  around current behavior first.
- acceptance: each of the four collectors has a fixture-backed test asserting its
  event shape (`source`, `timestamp`, `detail`, `project`) and empty/malformed-
  input handling.
- validation: `bash scripts/run_autotests.sh` green with the four new test files.
- dependencies: `tests/fixtures/`, the collector contract in
  `gittan-source-collector`.

---

## later

### Replace the raw 500-line gate with a complexity signal

- priority: later
- problem: `CLAUDE.md` mandates "split by responsibility rather than raising the
  limit," but the territory shows files trimmed to sit exactly under the cap:
  `core/report_service.py`, `core/mapping_review.py`, `core/config.py` are all
  **499**, with `setup_project_identity_wizard.py` at 497. The rule is being
  *gamed*, not honoured — line count measures the wrong thing, and CI stays green
  while complexity just shuffles between files.
- user value: A structure signal that tracks actual maintainability, so the gate
  encourages real decomposition instead of cosmetic line-shaving.
- non-goals:
  - Do not simply raise the 500 limit.
  - Do not mass-refactor the 499-line files in this item — first fix the *signal*.
- acceptance: a decision doc comparing options (keep lines + add a
  per-function/cyclomatic-complexity check, or replace line count outright), with
  a recommendation and a migration note. Implementation is a separate promoted
  item if the recommendation is GO.
- validation: the decision doc; no behavior change.
- dependencies: `scripts/check_file_lengths.py`, `.github/workflows/ci.yml`.

### Define a truth-payload versioning & migration policy

- priority: later
- problem: `core/engine_api.py` is documented as the *stable interface* for the
  Cursor extension, and `TRUTH_PAYLOAD_VERSION` is frozen at `"1"`
  (`core/truth_payload.py:11`) with no visible deprecation or migration path. The
  unknown is not a bug today — it is what breaks the extension the day the schema
  must change. Writing the policy now is cheap insurance; discovering the gap
  during a forced bump is not.
- user value: The extension and external callers get a documented compatibility
  contract instead of an implicit "hope nothing changes."
- non-goals: do not bump the version in this item; no schema change is needed
  yet.
- acceptance: a short policy — additive vs breaking change rules, how consumers
  detect the version, and the deprecation window — committed near
  `core/truth_payload.py`'s contract docs.
- validation: policy doc reviewed against the extension's actual consumption of
  the payload.
- dependencies: `core/truth_payload.py`, `core/engine_api.py`, `cursor-extension/`.

---

## Issue plan (on approval)

Per the skill's issue-lifecycle rule, the two `now` items and two `next` items
become issues via `/docs-to-issues` once this spec is approved; the two `later`
items stay as entries in this task-prompt until promoted. Set labels
`priority:now` / `priority:next` accordingly, and reflect on Project 3 if the
`project` gh scope is available.

## Open decisions before implementation

- **now / silent-failure:** is the degraded-source vocabulary already partly
  defined in `sources-and-flags.md`? Reuse it rather than inventing new statuses.
- **now / session spike:** confirm the real grouping order in
  `aggregate_report` before deciding whether the merge is a bug or a
  non-issue — the spike's first output is that yes/no.
- **next / consent audit:** decide whether a missing declaration should *fail
  CI* or just be reported, before adding any `--check`.
