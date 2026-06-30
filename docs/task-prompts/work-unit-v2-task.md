# Task Prompt: Work-unit v2 — report-first attribution (spike → slices)

Product direction: the **sacred contract** is `gittan report` output (Project-hour
review: customer → lines → hours → days, plus Uncategorized). Config shape, `gittan
map`, and `match_terms` mechanics are **not** sacred and may be replaced.

**Decision doc:** [`docs/decisions/work-unit-config-v2.md`](../decisions/work-unit-config-v2.md)  
**Workshop handout:** [`work-unit-brainstorm-agenda.md`](work-unit-brainstorm-agenda.md)  
**Operator acceptance (not in repo):** `~/.gittan/work-unit-acceptance.md` next to
`timelog_projects.json` — real customers, hours, and anchor cases for spike pass/fail.

Supersedes map-centric implementation paths under GH-222:
[`map-existing-project-and-merge-ux.md`](map-existing-project-and-merge-ux.md),
[`map-customer-first-flow.md`](map-customer-first-flow.md).

**Open PR disposition (decided 2026-06-30):** see [§ Open pull requests](#open-pull-requests-decided-2026-06-30).

Related (overlap / reuse): [`ab-rule-suggestions-task.md`](ab-rule-suggestions-task.md)
(uncategorized rule preview + confirm), [`setup-config-write-safety-task.md`](setup-config-write-safety-task.md)
(config write trust).

Fixtures and examples in **this** spec are **anonymized** — no live customer domains.

## Traceability

- story_id: `GH-222`
- spec_status: `draft`
- implementation_status: `not built`
- created_at: `2026-06-30`
- last_updated_at: `2026-06-30`
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: operator-local `~/.gittan/work-unit-acceptance.md`; spike report diff; `bash scripts/run_autotests.sh` on implementation slices
- validation.decision: `conditional GO`
- changelog:
  - `2026-06-30: Canonical PO backlog for report-first work-unit v2; supersedes map-first GH-222 implementation specs.`
  - `2026-06-30: Operator acceptance tables live under ~/.gittan/ per config hygiene.`
  - `2026-06-30: Open PR disposition decided — close #221–#224; land v2 docs via new PR.`

## Product framing

- **Problem:** v1 config + `gittan map` feel buggy — duplicate slug profiles, wrong
  `customer` buckets, large Uncategorized despite obvious anchors, URL-only review
  missing repo/cwd/title gaps.
- **Not the problem:** evidence collectors and session math when they already feed
  the report (fix attribution first).
- **Decision filter:** Does the next `gittan report` show the right table for the
  operator’s acceptance window? Not “was config updated”.

## Branch and mode defaults

- Spike and slices on short-lived `task/*` from latest `main`.
- Experiment on **copied** config (`cp` timestamped backup); never destructive edits
  to the only live `timelog_projects.json`.
- Do **not** merge [#221](https://github.com/mbjorke/timelog-extract/pull/221)–[#224](https://github.com/mbjorke/timelog-extract/pull/224) — close per [§ Open pull requests](#open-pull-requests-decided-2026-06-30).

## Open pull requests (decided 2026-06-30)

Report-first pivot supersedes v1 map investment. Branches remain on GitHub for
reference/cherry-pick; PRs are **closed, not merged**.

| PR | Branch | CI | Decision | Rationale |
|----|--------|-----|----------|-----------|
| [#221](https://github.com/mbjorke/timelog-extract/pull/221) | `task/map-anchor-attribution` | **Red** | **Close** | Map + collector mix; import failure; overlap with parked #223. Cherry-pick collector-only wins later via backlog item 6 (`task/report-evidence-*`), not this PR. |
| [#223](https://github.com/mbjorke/timelog-extract/pull/223) | `task/map-existing-project-merge-ux` | Green | **Close** | v1 map UX — wrong product bet vs work-unit v2. Branch useful for local experiments; do not merge to `main` before spike. |
| [#224](https://github.com/mbjorke/timelog-extract/pull/224) | `task/map-customer-first-flow` | Green | **Close** | Adds superseded `map-customer-first-flow.md`. Generic direction lands via new PR: `work-unit-config-v2.md` + `work-unit-v2-task.md`. |

**Close comment template (all three):**

> Superseded by report-first work-unit v2 — [`work-unit-v2-task.md`](docs/task-prompts/work-unit-v2-task.md) / [`work-unit-config-v2.md`](docs/decisions/work-unit-config-v2.md). Not merging v1 map path to `main`. Branch kept for reference; spike gates new attribution work (GH-222).

**After close:** one new docs PR from `main` with generic v2 decision + task spec (uncommitted locally). Implementation PRs link to `work-unit-v2-task.md` backlog items.

**Reopen only if:** spike NO-GO and explicit PO pass chooses v1 guardrails-only — then cherry-pick from #223 branch, not reopen as-is.

---

## Backlog

### 1. Time-boxed work-unit spike (proof on copied config)

- priority: **now**
- problem: Unclear whether v2 attribution is worth a larger build; operator distrusts
  config after map sessions.
- user value: Evidence that the **sacred report table** can be fixed without another
  map merge cycle or big-bang rewrite.
- non-goals: New production config schema; shipping merge/consolidate; committing
  operator-specific acceptance rows to the repo.
- behavior: Same collectors → improved classifier / anchor → existing **customer +
  line** (no new slug-only profile) → re-run report for the acceptance date window.
- acceptance:
  - Spike run documented against operator `~/.gittan/work-unit-acceptance.md` (period,
    target customers/lines, hour tolerance).
  - Uncategorized for the documented primary case moves toward ~0 without creating a
    duplicate profile whose `name` equals only a repo slug.
  - No hours moved between customers without an explicit preview step in the spike tool
    (manual notes OK for spike; productized in item 4).
- validation: Before/after `gittan report` for the acceptance window; config diff on
  **copy** only; spike notes appended to operator acceptance file or PR description
  (no private data in PR body).
- dependencies: Filled operator acceptance file; parked map PRs.

```gherkin
Feature: Work-unit spike proves report-first attribution
  Operators need proof before a larger v2 build.

  Scenario: Spike improves the sacred table without a new slug-only profile
    Given a copied projects config and an acceptance window in work-unit-acceptance.md
    When attribution maps anchor evidence to an existing customer and line
    Then the Project-hour review matches the acceptance table within documented tolerance
    And no new profile is created whose name equals only a repo slug
    And Uncategorized hours for the documented primary case drop toward zero
```

---

### 2. `gittan doctor` — config integrity warnings

- priority: **now**
- problem: Duplicate profiles and conflicting `customer` fields surface only at
  invoice time.
- user value: “Config feels buggy” becomes visible **before** report/map.
- non-goals: Silent auto-merge; auto-delete profiles; rewriting live config without
  confirm.
- behavior: Doctor emits warnings (and optional `doctor --json` entries) for:
  - same repo slug / anchor terms on multiple profiles with **different** `customer`;
  - “thin duplicate”: profile where `name` matches a repo leaf and has ≤N terms
    while another profile already carries richer terms for the same slug.
- acceptance:
  - Doctor warns on a fixture config with a thin slug duplicate + canonical line
    (anonymized fixture in `tests/`).
  - Doctor exit/docs mention fix path: attach anchor to existing line, remove duplicate
    (manual or future attribution UX).
  - `bash scripts/run_autotests.sh` passes.
- validation: Unit tests + doctor smoke on fixture; documented in PR.
- dependencies: None (may run parallel to spike).

```gherkin
Feature: Doctor surfaces dangerous project-config duplicates
  Operators should see config integrity issues before invoicing.

  Scenario: Thin slug duplicate is reported
    Given two profiles share the same repo slug in match_terms
    And they have different customer values
    When the operator runs gittan doctor
    Then the output includes a warning describing the duplicate slug and customer conflict
```

---

### 3. Close parked v1 map PRs (process)

- priority: **now**
- problem: Three open PRs (#221–#224) imply active v1 map investment and confuse reviewers.
- user value: Clear signal: report-first v2 is the path; no accidental merge.
- non-goals: Deleting remote branches; merging any of #221–#224 to `main`.
- behavior: Close all three PRs with supersede comment (template in § Open pull requests).
  Land generic v2 docs in a **new** PR from `main`.
- acceptance:
  - #221, #223, #224 closed on GitHub with link to this task.
  - No map-first code on `main` from these PRs.
  - Follow-up docs PR opened or queued for `work-unit-config-v2.md` + `work-unit-v2-task.md`.
- validation: `gh pr view` shows CLOSED; close comments present.
- dependencies: None.

---

### 4. Report-gap attribution UX (customer + line + preview)

- priority: **next**
- problem: `gittan map` and URL-only `gittan review` do not match how gaps appear
  (Uncategorized, anchor nudges: repo, cwd, session title).
- user value: One path from report pain → pick **existing** customer + line → preview
  hour impact → confirm write.
- non-goals: Default merge/consolidate into parent; create profile from slug without
  naming customer; reintroduce v1 map as the only path.
- behavior: New or redesigned command/surface (name TBD) triggered from report nudges
  or doctor; always shows customer, line, and hours delta before write; writes via
  safe config path with backup.
- acceptance:
  - Operator can move a documented uncategorized cluster to an existing line without
    a new slug-only profile.
  - Preview shows hours leaving Uncategorized and target customer/line.
  - Backup before write; `setup-config-write-safety` gates respected.
  - Tests cover preview math and no-create-when-existing-line-matches.
- validation: Unit tests; manual matrix scenario; `bash scripts/run_autotests.sh`.
- dependencies: Item 1 spike **conditional GO**; item 2 recommended.

```gherkin
Feature: Report-gap attribution without duplicate slug profiles
  Fixing the report must not create a new slug-named profile when a line already exists.

  Scenario: Operator assigns uncategorized evidence to an existing line
    Given a report with Uncategorized hours and anchor nudges for a repo slug
    And an existing profile line already represents that engagement under a customer
    When the operator confirms an hour-impact preview for that customer and line
    Then the next report moves those hours under that customer and line
    And the projects config does not gain a duplicate slug-only profile
```

---

### 5. Work-unit config schema + migrator

- priority: **later**
- problem: v1 `name` + `match_terms` soup does not model customer → work unit →
  signals cleanly.
- user value: Stable config that matches invoice mental model.
- non-goals: Big-bang migration without migrator; breaking truth_payload without
  version bump plan.
- behavior: Internal schema (customers + work_units or equivalent); migrator from v1;
  classifier targets report line keys; truth_payload evolution documented.
- acceptance: Migrator round-trip on anonymized fixture; report table unchanged in
  shape for sacred contract; operator migration runbook.
- validation: Fixture tests + manual migration on config copy.
- dependencies: Items 1–4; approved decision doc (`spec_status: approved`).

---

### 6. Cherry-pick collector / evidence wins (optional slice)

- priority: **later**
- problem: [#221](https://github.com/mbjorke/timelog-extract/pull/221) may contain
  evidence improvements buried under map scope.
- user value: Better input to classifier without adopting v1 map UX.
- non-goals: Merging full #221; map `--scan-repos` as default path.
- behavior: Extract disjoint collector/audit changes into `task/report-evidence-*`
  if spike needs them.
- acceptance: CI green; no new map command surface required for spike pass.
- validation: Autotests; collector fixture tests.
- dependencies: Spike evidence gaps only.

---

### 7. Total refactor (motor + config + all commands)

- priority: **do not build yet**
- problem: Tempting when everything feels broken.
- user value: None proven until spike fails success criteria.
- non-goals: Rewriting collectors, session engine, and CLI in one epic.
- behavior: Revisit only if item 1 NO-GO **and** doctor + write-safety still leave
  operator blocked.
- acceptance: N/A until reassessed by product-owner pass.
- validation: N/A.
- dependencies: Spike NO-GO post-mortem.

---

## Open decisions (before implementation slices)

- [ ] Spike time-box (suggest 1–2 days wall clock).
- [ ] Reuse vs replace [`ab-rule-suggestions-task.md`](ab-rule-suggestions-task.md) for
  uncategorized clusters in item 4.
- [ ] Rename vs retire `gittan map` command after item 4.
- [ ] truth_payload field rename (`project` → `line`) — defer to item 5.

## Behavior Contract

```gherkin
Feature: Work-unit v2 product backlog
  Report-first attribution is proven before map-centric v1 work continues.

  Scenario: Product owner backlog is the committed implementation spec
    Given a report-first work-unit planning pass is complete
    Then the canonical backlog lives in docs/task-prompts/work-unit-v2-task.md
    And map-first GH-222 specs are superseded or parked per this file
    And operator-specific acceptance tables remain outside the repository

  Scenario: Spike gates further map investment
    Given v1 map pull requests are parked
    When the work-unit spike passes operator acceptance
    Then implementation may proceed on items 2 and 4
    When the spike fails
    Then the team records NO-GO and does not merge parked map UX without a new PO pass
```

## Task output format for PR notes

1. Which backlog item(s) the PR addresses (number + title).
2. Spike or slice evidence (report before/after, doctor output) — **no private customer
   data** in PR text.
3. Test evidence (`run_autotests.sh`, targeted unittest).
4. Update this file’s Traceability (`implementation_status`, `implementation.pr`,
   `changelog`) when a slice lands.
