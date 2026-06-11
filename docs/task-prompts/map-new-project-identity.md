# Task Prompt: `gittan map` — new repository identity & billing fields

Product-owner backlog for fixing new-project mapping in `gittan map`: repo slug as
profile key, separate customer and display name, safe saves, and optional global
billing mode for freelancers.

Canonical behavior contracts use **anonymized** fixtures only (no live customer or
owner names in examples).

## Traceability

- story_id: `GH-pending`
- spec_status: `approved`
- implementation_status: `in progress`
- created_at: `2026-06-11`
- last_updated_at: `2026-06-11`
- implementation.pr: `pending`
- implementation.branch: `pending`
- implementation.commits: `[]`
- validation.evidence: `tests/test_mapping_review.py`, `tests/test_mapping_assistant.py`, `tests/test_config_compat.py`; manual `gittan map --last-week`
- validation.decision: `conditional GO`
- changelog:
  - `2026-06-11: Initial spec from map UX/debug session (slug vs customer confusion).`
  - `2026-06-11: Added billing_mode decision (direct default; agency global later).`
  - `2026-06-11: Anonymized all scenario data to customer-Y-faq-helper fixtures.`

## Problem

When mapping a new GitHub repository via `gittan map`, operators think in **customer**
and **engagement display names**, not config field names. Free-text “slug” prompts led
to:

- `name` set to a customer label (e.g. `Customer Y`) instead of repo slug
- `match_terms` polluted with lowercased customer strings
- Crashes after successful save (tuple unpacking in summary line)
- Unclear whether `customer` and `default_client` should differ

## Goal

1. **New repo mapping** produces profiles consistent with existing repo-style projects.
2. **Map asks only for operator-meaningful fields** — not JSON schema jargon.
3. **`default_client` = `customer` by default**; separate billing entity is global
   (freelancer/agency), not per map prompt.
4. **Duplicate merge** updates `match_terms` only — never renames profiles.

## Golden example (saved config)

After mapping `owner-a/customer-Y-faq-helper` with customer `Customer Y` and display
name `Customer Y Business Development`:

```json
{
  "name": "customer-Y-faq-helper",
  "project_id": "customer-Y-faq-helper",
  "customer": "Customer Y",
  "default_client": "Customer Y",
  "invoice_title": "Customer Y Business Development",
  "canonical_project": "customer-Y-faq-helper",
  "match_terms": [
    "customer-Y-faq-helper",
    "owner-a/customer-Y-faq-helper"
  ],
  "aliases": [
    "customer-Y-faq-helper",
    "Customer Y Business Development"
  ]
}
```

## Field semantics (do not confuse in UX copy)

| Field | Meaning | Set by map? |
| --- | --- | --- |
| `name` | Stable repo slug / profile key | Auto from repo |
| `customer` | Who the work is for (grouping, merge) | User prompt |
| `default_client` | Invoice/client line default | Same as `customer` in `direct` mode |
| `invoice_title` | Friendly label for invoices | Optional user prompt |
| `canonical_project` | Rollup across sibling profiles | Default = `name` on create |

## Billing mode (product decision)

### `direct` (default — most users)

- One map question: **Customer**
- `default_client` := `customer` on create
- Map **never** prompts for billing entity

### `agency` (freelancer / consultancy — **next slice**)

Top-level config (exact file TBD: `timelog_projects.json` root vs `~/.gittan` settings):

```json
{
  "billing_mode": "agency",
  "default_billing_entity": "Consultant Org AB"
}
```

- `customer` = end customer per project (map prompt)
- `default_client` = `default_billing_entity` on create
- Configured once in setup/doctor — **not** in each map flow

### Per-profile override

- **Later:** `gittan projects` advanced edit only
- **Non-goal:** extra map prompt for `default_client`

## Implementation status (2026-06-11)

| Item | Status |
| --- | --- |
| Repo slug auto; no free-text slug prompt | In progress (branch) |
| Customer + optional display name prompts | In progress |
| `invoice_title` + aliases on create | In progress |
| `match_terms` = slug + github slug only | In progress |
| `apply_mapping_changes` 4/5-tuple summary fix | In progress |
| `questionary` empty-string defaults | In progress |
| Map timing line + gh owner perf | In progress |
| Global `billing_mode` / `agency` | Not built |
| Repair misnamed profiles tool | Not built |
| Display name in terminal reports | Do not build yet |

## Behavior contracts

### Now — repo slug automatic

```gherkin
Feature: New repository mapping uses repo slug as profile name

  Background:
    Given timelog_projects.json has no profile for "customer-Y-faq-helper"
    And gittan map reports a new GitHub repo "owner-a/customer-Y-faq-helper"

  Scenario: Add as new project without typing a slug
    When the user chooses "Add as new project"
    Then gittan shows the derived slug "customer-Y-faq-helper" as read-only context
    And gittan does not prompt for a free-text project slug
    And the user is prompted only for customer and optional display name

  Scenario: Customer and display name are saved with repo slug as name
    When the user enters customer "Customer Y"
    And the user enters display name "Customer Y Business Development"
    And the user confirms save
    Then the saved profile has name "customer-Y-faq-helper"
    And the saved profile does not use "Customer Y" as name
```

### Now — customer and display name

```gherkin
Feature: New project identity fields in gittan map

  Background:
    Given billing_mode is "direct" or unset
    And the user chose "Add as new project" for "owner-a/customer-Y-faq-helper"

  Scenario: Customer and display name map to correct config fields
    When the user enters customer "Customer Y"
    And the user enters display name "Customer Y Business Development"
    Then the saved profile has customer "Customer Y"
    And the saved profile has default_client "Customer Y"
    And the saved profile has invoice_title "Customer Y Business Development"
    And aliases include "customer-Y-faq-helper" and "Customer Y Business Development"
    And gittan does not prompt for a separate billing entity

  Scenario: Display name is optional
    When the user enters customer "Customer Y"
    And the user leaves display name empty
    Then invoice_title is empty
    And name remains "customer-Y-faq-helper"

  Scenario: Prompt defaults are empty strings
    When gittan prompts for customer
    Then the input default is empty
    When gittan prompts for display name
    Then the input default is empty
```

### Now — match_terms

```gherkin
Feature: Match terms for a newly mapped repository

  Scenario: New repo adds github slug and repo stem only
    Given the user saved a new profile for "owner-a/customer-Y-faq-helper"
    Then match_terms contain "customer-Y-faq-helper"
    And match_terms contain "owner-a/customer-Y-faq-helper"
    And match_terms do not contain "customer y"
    And match_terms do not contain the display name lowercased
```

### Now — save without crash

```gherkin
Feature: Apply mapping changes summary

  Scenario: New project with customer metadata saves successfully
    Given additions include customer and invoice_title on the first row
    When apply_mapping_changes runs
    Then the config file is written
    And a green summary line is printed
    And no exception is raised
```

### Now — duplicate slug guard

```gherkin
Feature: Duplicate repo slug guard in map

  Scenario: Slug already in config
    Given a profile named "customer-Y-faq-helper" already exists
    When the user chooses "Add as new project" for the same repo
    Then gittan explains the slug is already mapped
    And gittan skips customer prompts for that repo
    And the user can choose "Map to existing project" instead
```

### Now — duplicate merge identity

```gherkin
Feature: Duplicate group merge in gittan map

  Background:
    Given profiles "project-alpha" and "project-alpha-dev" for customer "customer-a.example"
    And gittan map shows a duplicate group targeting "project-alpha"

  Scenario: Merge adds variants to canonical project
    When the user chooses "Merge (default)"
    Then match_terms on "project-alpha" include all repo variants
    And github slugs are removed from sibling profiles' match_terms
    And sibling profile rows are kept
    And name on "project-alpha" is unchanged
    And canonical_project on "project-alpha" is unchanged
```

### Next — map timing

```gherkin
Feature: gittan map collection timing

  Scenario: User sees timing after spinner
    When gittan map finishes collecting signals
    Then the CLI prints total seconds and split between report and mapping review
```

### Next — GitHub discovery performance

```gherkin
Feature: GitHub repo discovery for map

  Scenario: Only real GitHub owners are queried
    Given profiles with match_terms "owner-a/project-beta"
    And tracked_urls "https://example-social.test/groups/demo"
    When collect_gh_repo_list_data runs
    Then owners queried are derived from match_terms slugs only
    And "example-social.test" is not queried as a GitHub owner
```

### Next — global billing mode

```gherkin
Feature: Global billing mode in projects config

  Background:
    Given timelog_projects.json has billing_mode "agency"
    And default_billing_entity is "Consultant Org AB"

  Scenario: New project inherits global billing entity
    When the user adds repo "owner-a/customer-Y-faq-helper"
    And the user enters customer "Customer Y"
    Then the saved profile has customer "Customer Y"
    And the saved profile has default_client "Consultant Org AB"

  Scenario: Direct mode keeps customer and default_client aligned
    Given billing_mode is "direct"
    When the user enters customer "Customer Y"
    Then default_client is "Customer Y"

  Scenario: Map does not ask about freelancer billing
    When the user runs gittan map
    Then gittan never prompts for default_client or billing entity
```

### Later — repair misnamed profile

```gherkin
Feature: Repair misnamed project profile

  Scenario: Rename profile while preserving customer and invoice title
    Given a profile with name "Customer Y" and match_terms including "owner-a/customer-Y-faq-helper"
    When the user runs a repair or projects edit flow
    Then the profile can be renamed to "customer-Y-faq-helper"
    And customer and invoice_title are preserved
    And match_terms are normalized to slug and github slug
```

## UX copy rules (map)

- Say **Customer (who you bill)** — not `customer` / `default_client`.
- Say **Display name (optional, for invoices)** — not `invoice_title`.
- Show **Project slug (from repo): customer-Y-faq-helper** as read-only context.
- Do **not** say “project profile”, “config key”, or backtick JSON field names in prompts.
- Do **not** ask for billing entity unless `billing_mode` is `agency` (then still no map
  prompt — use global entity only).

## Safety constraints

- Never move/delete `timelog_projects.json`; backup before write (existing behavior).
- Map changes require explicit user approval per repo / duplicate group.
- No live customer, owner, or home paths in tests, fixtures, or this spec.

## Acceptance criteria (`now` slice)

- [ ] New repo flow matches golden example JSON shape.
- [ ] No slug free-text prompt; repo stem is the profile `name`.
- [ ] `customer` prompt only; `default_client` copied from `customer` in direct mode.
- [ ] Optional display name → `invoice_title` + `aliases`.
- [ ] `apply_mapping_changes` handles 3/4/5-tuples without crash after save.
- [ ] Duplicate slug skips add flow with clear message.
- [ ] Merge does not change `name` or `canonical_project` on target profile.
- [ ] `bash scripts/run_autotests.sh` green on branch.

## Validation

1. Unit: `tests/test_mapping_review.py`, `tests/test_mapping_assistant.py`,
   `tests/test_config_compat.py`, `tests/test_gh_repo_discovery.py`
2. CLI smoke: `bash scripts/cli_impact_smoke.sh` after CLI-facing edits
3. Manual: `pip install -e .` then `gittan map --last-week` with fixture repo
   `owner-a/customer-Y-faq-helper`; verify saved config against golden example

## Related code (starting points)

- `core/mapping_review.py` — review builder, prompts, batch UX
- `core/mapping_assistant.py` — `apply_mapping_changes`
- `core/config.py` — `apply_rule_to_project`, `normalize_profile`
- `core/cli_map.py` — map entry, timing
- `core/gh_repo_discovery.py` — owner filter + cache
- `timelog_projects.example.json` — `_profile_field_guide`

## Non-goals

- Renaming `name` field in schema (deprecation) in this slice
- Showing `invoice_title` instead of slug in terminal reports
- Automatic migration of historically misnamed profiles
- Per-map prompt for `default_client` in agency mode
