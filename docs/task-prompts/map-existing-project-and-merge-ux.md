# Task Prompt: `gittan map` — map to existing project & understandable merge

Problem specification from a 2026-06-30 mapping session: operators with mature
`timelog_projects.json` configs hit **wrong-project attribution** because map
defaults to **create** or **merge-to-parent** instead of **add term to the right
existing profile**. Merge UX is opaque and contradicts intentional parent/dev
splits.

**Superseded for implementation** by report-first backlog
[`work-unit-v2-task.md`](work-unit-v2-task.md) — PR #223 closed; do not extend map UX
until spike passes. Kept as historical problem record for GH-222.

Related: [`map-new-project-identity.md`](map-new-project-identity.md) (new-repo
fields), [`repo-slug-project-attribution.md`](repo-slug-project-attribution.md)
(worktree slug anchors), [`map-customer-first-flow.md`](map-customer-first-flow.md)
(customer-first UX — also superseded by work-unit v2).

Fixtures below are **anonymized** — no live customer or owner names.

## Traceability

- story_id: `GH-222`
- spec_status: `superseded`
- implementation_status: `not built`
- created_at: `2026-06-30`
- last_updated_at: `2026-06-30`
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/223 (closed)
- implementation.branch: `task/map-existing-project-merge-ux` (closed)
- implementation.commits: []
- validation.evidence: superseded by `work-unit-v2-task.md` item 1 (spike)
- validation.decision: `NO-GO`
- changelog:
  - `2026-06-30: Problem spec from map session — create/merge vs map-to-existing; merge UX opaque.`
  - `2026-06-30: GH-222 opened; implementation started on task/map-existing-project-merge-ux.`
  - `2026-06-30: Follow-up spec map-customer-first-flow.md (customer → engagement UX).`
  - `2026-06-30: Superseded — report-first backlog work-unit-v2-task.md; PR #223 closed.`

## Problem (one sentence)

**Map cannot reliably attach unmapped activity to an existing project; it treats
gaps as new projects or duplicate families to merge, which moves `match_terms`
between profiles without a clear preview and breaks intentional billing splits.**

## Observed symptoms

1. **New or mis-targeted profiles** — anchor values chosen as “Create new project”
   become profile names via `apply_rule_to_project` (customer defaults to project
   name when omitted).
2. **Terms moved between siblings** — duplicate “Merge (default)” added repo
   variants to the parent profile and removed GitHub slugs from a `-dev` sibling
   while keeping both profile rows.
3. **Repeated nagging** — same repo family reappears in map because sibling
   profiles still “own” part of the family or terms remain split across profiles.
4. **Wrong billing bucket** — hours shift customer/project without an explicit
   customer step in anchor or duplicate flows.

## Root causes (code)

| Area | Behavior today | Operator impact |
| --- | --- | --- |
| Anchor flow (`core/anchor_nudge.py`) | Lists existing projects + “Create new project: {value}”; no suggestion | Easy to create `prospect-faq-helper`-style names instead of picking `customer-Y-faq` |
| Repo scan (`core/mapping_review_flow.py`) | Default **Add as new project**; “Map to existing” is second choice | New repo path creates duplicates when profile already exists under another slug |
| Duplicate groups (`core/mapping_review.py`, `core/mapping_review_flow.py`) | Auto `merge_target_for_customer()` → non-`-dev` parent; only **Merge (default)** or Skip | Dev/hash-fork activity consolidated onto parent; no “add slug to `-dev` profile” |
| Merge effect (`_merge_additions_for_change`, `_merge_removals_for_change`) | Adds all family slugs + stems to target; strips github slugs from same-customer siblings | Parent gains `project-alpha-dev` stem; dev profile loses github terms |
| Classification gap | Signal “unmapped” when related profile exists but term missing | Tool offers create/merge, not “missing term on existing profile” |

## Mental model vs tool behavior

### Operator model (golden)

Two deliberate billing projects under one customer:

| Profile | Billing GitHub slug |
| --- | --- |
| `project-alpha` | `owner-a/project-alpha` |
| `project-alpha-dev` | `owner-a/project-alpha-dev-31e799cf` (active hash fork) |

Stale slug `owner-a/project-alpha-dev` (no hash) must **not** become the primary
identity when the hash fork has activity.

### What “Merge (default)” actually does

Sounds like: combine two projects or pick one repo.

Actually:

1. Adds **canonical slug + every duplicate variant + repo stem** to
   `merge_target` (usually parent `project-alpha`).
2. Removes **github slugs in the same repo family** from sibling profiles (same
   `customer`); profile rows remain.
3. Never shows a term-level diff before apply.

This is **term relocation + bulk add to parent**, not project merge in the
Git sense.

### Why merge feels incomprehensible

1. **Hidden target** — user never picks merge destination; parent wins by rule.
2. **Internal labels** — “Canonical billing repo”, “Primary — local working copy”,
   “Duplicate — remote only”; recency dot on one line only.
3. **No preview** — no list of terms added/removed per profile or customer impact.
4. **Binary choice** — Merge (default) | Skip; no map-to-existing in duplicate step.
5. **Contradicts parent/dev split** — intentional siblings treated as duplicates.

## Goal

1. **Map to existing project** is the primary path in **all** map steps (anchors,
   new repos, duplicate groups).
2. **Create project** and **merge family** are opt-in, with explicit preview.
3. **Intentional parent/dev splits** are preserved unless the operator explicitly
   consolidates.
4. **Hash-fork slugs** stay first-class billing identities when they carry activity
   (do not collapse to stem-only `-dev` in UX copy or default targets).

## Non-goals (this spec)

- Manual config restore or one-off `timelog_projects.json` edits.
- Re-introducing slow default `--scan-repos` / full git+GitHub discovery on every
  `gittan map` run.
- Changing session-hour math or collector evidence contracts.

## Acceptance criteria

### Now — anchor flow prefers existing

```gherkin
Feature: Map anchors to existing projects

  Background:
    Given profile "customer-Y-faq" exists with customer "Customer Y"
    And unmapped anchor "customer-Y-faq-helper" appears in the report window

  Scenario: Suggest existing project before create
    When the user runs gittan map interactively
    Then the anchor prompt suggests "customer-Y-faq" as the default or top choice
    And "Create new project" is not the default selection

  Scenario: Apply to existing does not create a profile
    When the user maps the anchor to "customer-Y-faq"
    Then match_terms on "customer-Y-faq" include the anchor value
    And no new project row is created
```

### Now — duplicate group: map to existing, not only merge

```gherkin
Feature: Duplicate repo family handling

  Background:
    Given profiles "project-alpha" and "project-alpha-dev" for customer "customer-a.example"
    And activity is on slug "owner-a/project-alpha-dev-31e799cf"
    And gittan map shows a duplicate group for that family

  Scenario: Map hash fork to dev profile without merge
    When the user chooses "Add slug to existing project"
    And selects "project-alpha-dev"
    Then match_terms on "project-alpha-dev" include "owner-a/project-alpha-dev-31e799cf"
    And match_terms on "project-alpha" are unchanged
    And the duplicate group does not reappear on the next map for the same window

  Scenario: Merge requires explicit preview
    When the user chooses merge/consolidate
    Then gittan shows terms added to the target profile and terms removed from siblings
    And merge is not the default when a "-dev" sibling profile exists
```

### Now — merge copy matches effect

```gherkin
Feature: Understandable merge language

  Scenario: Merge prompt names target and consequences
    When gittan offers family consolidation
    Then the prompt names the target profile explicitly
    And lists github slugs that will be added to the target
    And lists github slugs that will be removed from sibling profiles
    And does not use "Merge (default)" without that preview
```

### Now — new repo default

```gherkin
Feature: New repo mapping default

  Scenario: Existing profile match
    Given profile "project-alpha-dev" exists
    When gittan map proposes repo "owner-a/project-alpha-dev-31e799cf"
    Then the default action is "Map to existing project" with "project-alpha-dev" suggested
    And "Add as new project" is not the default
```

## Implementation notes (for builders)

- Touch points: `core/anchor_nudge.py`, `core/mapping_review_flow.py`,
  `core/mapping_review.py` (`merge_target_for_customer`, duplicate grouping),
  `core/mapping_suggestions.py` (reuse nearby-github / activity hints for anchor
  defaults).
- Preserve [`map-new-project-identity.md`](map-new-project-identity.md) customer
  prompts on **create** path only.
- Tests: extend `tests/test_mapping_review_merge.py` and anchor flow tests with
  anonymized parent/dev/hash-fork fixtures; add UX-default tests where questionary
  defaults are asserted via injected chooser hooks.

## Validation plan

1. Fixture config with `project-alpha` + `project-alpha-dev` and events on hash
   fork slug only — map must offer add-to-dev without parent merge.
2. Replay anonymized anchor list — no new profiles created when existing match
   is chosen.
3. `bash scripts/run_autotests.sh` green after implementation.
4. Manual: `gittan map --last-week` on maintainer config — duplicate group either
   resolved in one pass or skipped with clear reason; no silent term moves.
