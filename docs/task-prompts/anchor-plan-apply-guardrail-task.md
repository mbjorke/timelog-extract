# Task Prompt: Stop bulk anchor-plan → config (guardrail before work-unit v2)

## Traceability

- story_id: `GH-342`
- spec_status: `approved`
- implementation_status: `not built`
- created_at: `2026-07-09`
- last_updated_at: `2026-07-09`
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: `NO-GO`
- changelog:
  - `2026-07-09: PO pass — operator nearly applied 96-candidate anchor plan (min_hits:1) including branch/label junk; formalize guardrail + nudge redirect ahead of v2 spike.`

## Product framing

**Sacred contract** (unchanged): `gittan report` Project-hour review
(customer → lines → hours → days). Config shape and `match_terms` are **not**
sacred — see [`work-unit-config-v2.md`](../decisions/work-unit-config-v2.md).

**Operator incident (2026-07-09):** `projects-audit --write-anchor-plan` produced
~96 candidates at `min_hits: 1`, treating `repo` / `dir` / `branch` / `label`
equally. Applying that plan would have written hundreds of permanent
`match_terms` (`head`, `pull requests`, every feature branch) and made config
unmaintainable. Gut check: **anchor-plan is an inventory, not a config
to apply.**

This is the same failure mode GH-222 / work-unit v2 already named — "the fix is
not better map + more match_terms" — but **implementation and nudges still point
operators at bulk apply**. Guard the dangerous path **now**; do not wait for the
full v2 spike.

Related:

| Spec / issue | Role |
| --- | --- |
| [`work-unit-v2-task.md`](work-unit-v2-task.md) / #267 | Report-first attribution (spike → UX) — **next** after guardrail |
| [`working-directory-anchor-signal.md`](../specs/working-directory-anchor-signal.md) | Anchor kinds; `label` weakest for auto-suggest |
| [`triage-ux.md`](../specs/triage-ux.md) | Signal-scope first; review confirms, does not archaeology |
| #262 | Repo-slug worktree-invariant attribution |
| #222 | Symptom: map cannot attach to existing line cleanly |

## Decision filter

1. Does the next change make it **harder** to dump branch/label junk into live
   `timelog_projects.json`?
2. Does the nudge point at **existing customer + line** (or repo/dir only), not
   "write the whole plan"?
3. If neither — park it under work-unit v2; do not polish map UX.

## Backlog

### 1. Anchor-plan apply guardrail (kinds + floor)

- priority: **now**
- problem: `build_anchor_plan_from_audit` / `projects-anchor` accept every
  unanchored kind at `min_hits: 1`, so a month-long audit becomes a "fix config"
  temptation.
- user value: Operators can still **inventory** signals; they cannot accidentally
  promote feature branches and UI titles into permanent rules.
- non-goals: Deleting `projects-anchor`; inventing work-unit schema; auto-mapping
  to existing lines (that is item 3 / v2 item 4).
- behavior:

```gherkin
Feature: Anchor plans do not bulk-propose ephemeral kinds
  Inventory stays useful; apply stays safe.

  Scenario: Default plan excludes branch and label from apply candidates
    Given an audit with unanchored repo, dir, branch, and label signals
    When the operator writes an anchor plan with default settings
    Then repo and dir candidates may appear as apply candidates
    And branch and label appear only under a diagnostic / inventory section
      (or require an explicit --include-ephemeral-kinds flag)
    And the plan meta states that branch/label are not default apply targets

  Scenario: Default min_hits floor blocks one-off noise
    Given default plan generation (no override)
    When candidates are written
    Then apply candidates require min_hits >= 20 (or documented product floor)
    And min_hits: 1 is only available behind an explicit --unsafe-low-floor flag
      that prints a warning

  Scenario: projects-anchor refuses junk kinds without override
    Given a hand-edited plan that still lists branch/label apply rows
    When the operator runs projects-anchor without --include-ephemeral-kinds
    Then those rows are skipped with a clear reason
    And repo/dir rows still apply (dry-run + backup unchanged)
```

- acceptance:
  - Default `--write-anchor-plan` does not emit branch/label as **apply**
    candidates (inventory OK if clearly labeled).
  - Default `min_hits` for apply candidates ≥ 20 (tunable constant; document in
    CLI help + `working-directory-anchor-signal.md`).
  - `projects-anchor` skips ephemeral kinds unless opted in; exit non-zero or
    warn loudly if the plan was *only* ephemeral rows.
  - Unit tests cover plan builder + apply filter; `bash scripts/run_autotests.sh`.
- validation: Fixture audit with mixed kinds; assert plan JSON shape; apply
  dry-run on a plan that mixes repo + branch.
- dependencies: None.

---

### 2. Nudge copy + tool routing (stop pointing at bulk apply)

- priority: **now**
- problem: `status` / `report` nudges and help text still suggest
  `projects-audit --write-anchor-plan` / interactive map as the fix for
  unanchored activity — which steers operators into item 1's failure mode.
- user value: Pain → right verb: **repo/dir → attach to existing line**;
  **branch/label → review/preview or ignore**, not config.
- non-goals: Full triage command rename; Ink overlay; implementing v2 preview UX.
- behavior:

```gherkin
Feature: Unanchored nudges route by anchor kind
  The modal wall must not advertise bulk config write as the default fix.

  Scenario: Repo or dir nudge suggests existing-line mapping
    Given unanchored repo or dir signals above the nudge floor
    When status or report shows the nudge
    Then the copy names attaching the signal to an existing customer/line
      (or gittan map / review path that does that)
    And it does not recommend writing a full month anchor-plan as the primary action

  Scenario: Branch or label nudge does not push match_terms
    Given only branch/label unanchored signals
    When the nudge is shown
    Then copy treats them as session context / review candidates
    And does not suggest projects-anchor or permanent match_terms
```

- acceptance:
  - `core/report_nudges.py` / `core/anchor_nudge.py` / CLI help strings updated.
  - Docs: `cli-command-map.md` + one paragraph in
    `working-directory-anchor-signal.md` § suggestion/apply.
  - Manual smoke: `gittan report` / `status` copy reviewed on a fixture day.
- validation: String/unit tests for nudge builders; doc link in PR.
- dependencies: Item 1 preferred first (same PR OK if small).

---

### 3. Promote work-unit v2 spike + report-gap UX

- priority: **next**
- problem: Guardrails stop the bleed; they do not fix Uncategorized when the
  right line already exists.
- user value: Choose **customer + existing line → preview hours → confirm** —
  the sacred table improves without a new slug-only profile.
- non-goals: Shipping v1 map polish (#221–#224 path); bulk create profiles.
- behavior: Execute [`work-unit-v2-task.md`](work-unit-v2-task.md) items **1**
  (spike) then **4** (report-gap attribution UX). Keep #267 as the tracking
  issue; bump label to `priority:now` when item 1–2 of *this* spec land.
- acceptance: As written in work-unit-v2-task.md items 1 and 4.
- validation: Operator-local acceptance file; before/after report.
- dependencies: Items 1–2 of this spec (or explicit PO waiver).

---

### 4. Doctor: thin slug / conflicting customer (reuse v2 item 2)

- priority: **next**
- problem: Duplicate slug profiles still hide until invoice time.
- user value: See integrity issues before another map session.
- non-goals: Auto-merge.
- behavior: Same as work-unit-v2-task.md item 2 — implement under that story or
  cherry-pick into the same lane as item 3.
- acceptance / validation: Per work-unit-v2-task.md.
- dependencies: None (parallel to spike).

---

### 5. Unified `gittan triage` verb

- priority: **later**
- problem: Signal / session / event scopes are split across audit, map, review,
  nudge.
- user value: One funnel per [`triage-ux.md`](../specs/triage-ux.md).
- non-goals: Building triage before guardrail + v2 preview exist.
- behavior: Spec already drafted; promote only after item 3 GO.
- acceptance: Separate PO pass when promoted.
- dependencies: Items 1–3.

---

### 6. Do not build yet

| Idea | Why parked |
| --- | --- |
| Default path / friendlier nudge that still opens full anchor-plan apply | Makes wrong config **faster** |
| Profile-per-branch or profile-per-session-title | Ephemeral identity ≠ invoice line |
| Auto-apply anchor-plan without human project choice | Violates triage honesty boundary |
| Reopening closed v1 map PRs (#221–#224) as the path | Superseded by report-first v2 |

## Practical operator guidance (until items land)

| Do | Don't |
| --- | --- |
| Keep ~10–20 stable profiles with **repo** slugs | Create a profile per branch |
| `gittan map --last-week` for **new repos** only | Month-long map driven by anchor nudges |
| Manually attach 2–3 **dir** → existing line | `projects-anchor -i` on the whole plan |
| Treat `projects-audit` as **diagnostics** | Treat the plan as "fix everything" |

## Issue

Tracking issue: [#342](https://github.com/mbjorke/timelog-extract/issues/342). #267 (v2 spike) stays `priority:next` until this guardrail merges, then promote #267 to `now`.

## Non-goals for this PO pass

- Writing implementation code (except committing this spec).
- Changing presence / billable work (#327 Slice 1 already merged).
- Installing launchd for #237 (separate track).
