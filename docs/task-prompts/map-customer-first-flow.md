# Task Prompt: `gittan map` — customer-first mapping (then engagement profile)

Product requirement: operators think **customer** (who to bill), not config field
`name`. Map should mirror that mental model — **choose customer first**, then
**choose or create the engagement profile** under that customer. Only then write
`match_terms` (and optionally confirm `customer` / `default_client` on create).

**Superseded for implementation** by [`work-unit-v2-task.md`](work-unit-v2-task.md)
(report-first attribution). Historical map UX intent below.

Was intended to extend [`map-existing-project-and-merge-ux.md`](map-existing-project-and-merge-ux.md)
(GH-222).

Fixtures are **anonymized**.

## Traceability

- story_id: `GH-222`
- spec_status: `superseded`
- implementation_status: `not built`
- created_at: `2026-06-30`
- last_updated_at: `2026-06-30`
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/224 (closed)
- implementation.branch: `task/map-customer-first-flow` (closed)
- implementation.commits: []
- validation.evidence: superseded by `work-unit-v2-task.md`
- validation.decision: `NO-GO`
- changelog:
  - `2026-06-30: Customer-first map flow spec — operator maps to customer, then engagement profile.`
  - `2026-06-30: Superseded — report-first work-unit-v2-task.md replaces map-centric UX plan.`

## Problem

Today “map to project” means: **append a string to `match_terms` on a profile
row**. Classification uses terms; **`customer` is not consulted for matching**.

Operators instead want: **“this activity belongs to customer X”** — with project
as an optional sub-bucket (prod/dev, repo line, engagement name).

Symptoms when map stays project-first:

- Correct-looking profile, wrong `customer` (e.g. engagement profile with
  `customer: operator-name` while work is for `customer-y.example`).
- Flat list of 39 project names — no grouping by who you invoice.
- “Create new project” feels like creating a customer; it only creates a new
  classification row with `customer := project_name`.

Setup wizard already maps **customer → projects** (`setup_project_identity_wizard.py`).
**Map does not** — that asymmetry causes repeat damage on mature configs.

## Mental model (target)

```
Activity signal (anchor / repo slug)
        ↓
   Which CUSTOMER?          ← primary question (billing)
        ↓
   Which ENGAGEMENT?        ← profile under that customer (optional split)
        ↓
   Add match_term(s)       ← technical effect (unchanged engine)
```

| Operator term | Config field | Example |
| --- | --- | --- |
| Customer (who you bill) | `customer`, `default_client` | `customer-y.example` |
| Engagement / project line | `name`, `match_terms` | `customer-Y-faq-helper` |
| Invoice label (optional) | `invoice_title` | `Customer Y — FAQ chatbot` |

**Classification still runs on `match_terms`** — this spec changes **map UX and
write safety**, not `classify_project()` unless we later add customer-scoped
fallback (non-goal here).

## Target UX (all map surfaces)

### Shared rules

1. **Never** show a flat list of all profile names as the first step.
2. **Always** show `customer` in prompts: `customer-Y-faq-helper [customer-y.example]`.
3. **Create path** requires explicit customer (reuse `prompt_new_project_fields` /
   setup wizard patterns — `_existing_customers()`).
4. **Preview before save:** customer, target profile, terms in (+ none removed
   unless consolidate opt-in from GH-222).
5. Reuse suggestion helpers (`map_project_suggest.py`) to pre-select customer +
   profile, not profile alone.

### Anchor flow (step 1 of `gittan map`)

For each unmapped anchor:

```
Signal: working directory "customer-Y-faq-helper" (112 events)

1. Customer: [customer-y.example ▼]  (suggested from nearby profiles / fuzzy match)
2. Engagement under that customer:
     • customer-Y-faq-helper  (suggested — repo slug match)
     • customer-faq           (sibling)
     • + New engagement…
     • Skip
3. Preview: add match_term "customer-Y-faq-helper" → customer-Y-faq-helper
            customer remains customer-y.example
```

If only one profile exists for the customer, **skip step 2** (or show as confirmation).

### New repo (`--scan-repos`)

```
Repo: owner-a/customer-Y-faq-helper-dev-31e799cf

1. Customer: customer-y.example
2. Engagement: customer-Y-faq-helper-dev (suggested)
3. Action default: Add slug to existing engagement (not new row)
```

### Duplicate / repo-family group

```
Customer: customer-a.example
Variants: project-alpha, project-alpha-dev-31e799cf

1. Customer: customer-a.example  (read-only if inferred)
2. Add slugs to engagement: project-alpha-dev  (suggested)
   OR consolidate (opt-in, preview, confirm) — per GH-222
```

## Suggestion logic (customer → profile)

Extend `map_project_suggest.py` (or sibling module):

| Step | Input | Output |
| --- | --- | --- |
| Suggest customer | anchor / slug / events | `customer` string from best matching profile, or ranked list |
| Suggest profile | customer + signal | profile `name` under that customer only |

Rules:

- Hash-fork slugs prefer `-dev` engagement under same customer (existing rule).
- Fuzzy anchor match (`customer-Y-faq-helper` → profile whose name contains `faq`)
  **within customer shortlist first**, then global.
- If suggested profile’s `customer` ≠ chosen customer → **warn** before apply.

Reuse from setup: `_existing_customers()`, `_candidate_projects_for_customer_mapping()`.

## Golden example (after map)

Operator maps `customer-Y-faq-helper` cwd to customer `Customer Y`, engagement
`customer-Y-faq-helper`:

```json
{
  "name": "customer-Y-faq-helper",
  "customer": "Customer Y",
  "default_client": "Customer Y",
  "match_terms": [
    "customer-Y-faq-helper",
    "owner-a/customer-Y-faq-helper",
    "lovable banking chatbot admin interface"
  ]
}
```

Not: terms on `customer-faq` while `customer` stays `operator-name`.

## Non-goals

- Replacing project-based hour reports with customer-only reports (display may
  group by customer later; out of scope).
- Auto-rewriting `customer` on existing profiles when remapping terms (warn only;
  separate “fix customer” action if needed).
- Changing collector / anchor extraction.

## Acceptance criteria

### Customer-first anchor flow

```gherkin
Feature: Map anchors customer-first

  Background:
    Given profiles "customer-Y-faq-helper" and "customer-faq" both for customer "Customer Y"
    And unmapped anchor "customer-Y-faq-helper" (working directory)

  Scenario: Operator selects customer before engagement
    When gittan map prompts for the anchor
    Then the first question is which customer to bill
    And "Customer Y" is suggested
    And the second question lists only engagements under "Customer Y"
    And "customer-Y-faq-helper" is suggested

  Scenario: Terms apply with customer visible in preview
    When the operator confirms
    Then the preview shows customer "Customer Y" and engagement "customer-Y-faq-helper"
    And match_terms on that engagement include "customer-Y-faq-helper"
    And customer on that engagement remains "Customer Y"
```

### Customer mismatch guard

```gherkin
  Scenario: Warn when engagement customer differs from chosen customer
    Given profile "legacy-faq" has customer "operator-name"
    And the operator chose customer "Customer Y"
    When they select engagement "legacy-faq"
    Then gittan warns that customer will not match
    And does not save without explicit confirmation
```

### New engagement requires customer

```gherkin
  Scenario: Create engagement under chosen customer
    Given customer "Customer Y" is selected
    When the operator chooses "New engagement"
    Then gittan prompts for engagement slug (from repo if available)
    And saves customer "Customer Y" on the new profile
    And does not default customer to the anchor string alone
```

### Parity with setup wizard

```gherkin
  Scenario: Customer list matches setup wizard source
    When map builds the customer dropdown
    Then it uses the same curated customer list as setup identity wizard
    And does not list raw profile names as customers
```

## Implementation notes

| Area | Change |
| --- | --- |
| `core/anchor_nudge.py` | Two-step (customer → engagement); preview panel |
| `core/mapping_review_flow.py` | Same pattern for new repo + duplicate groups |
| `core/map_project_suggest.py` | `suggest_customer_for_signal`, `profiles_for_customer` |
| `core/setup_project_identity_wizard.py` | Extract shared customer list helpers (avoid duplication) |
| Tests | `tests/test_map_customer_first_flow.py`; extend anchor + batch review tests |

PR #223 remains valid incremental fix; **merge it**, then implement this spec as
a follow-up PR on `task/map-customer-first-flow`.

## Validation plan

1. Fixture config: two engagements under one customer; map anchor → correct
   customer + engagement without flat 39-name list.
2. Regression: `customer-Y-faq-helper` anchor must not land on `customer-faq` when
   `customer` differs unless operator explicitly confirms.
3. `bash scripts/run_autotests.sh` green.
4. Manual asciniema / maintainer walkthrough: map three anchors; report shows
   hours under expected customer line on invoice export.
