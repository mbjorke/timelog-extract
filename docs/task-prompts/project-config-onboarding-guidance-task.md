# Project config onboarding guidance

Product-owner backlog for the next low-conflict slice: make Gittan tell users the
next safe project-config step across `doctor`, `setup`, and `review`, without
touching reported-time semantics or source-collector behavior.

This is intentionally adjacent to, not part of, the active reported-time and
collector PR work. Implementation should avoid `core/report_service.py`,
reported-time sync code, and source-specific collector parsing unless a later
task explicitly changes that scope.

## Traceability

- story_id: GH-197
- spec_status: approved
- implementation_status: not built
- created_at: 2026-06-26
- last_updated_at: 2026-06-26
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: conditional GO
- changelog:
  - 2026-06-26: Initial product-owner task created as the next low-conflict backlog item while reported-time and Zed collector PRs remain active.

## Why this is next

The strongest current product bet that does not collide with the active PR stack
is simplifying project configuration. The existing direction is already stated in
`docs/ideas/opportunities.md` and `docs/sources/ai-assisted-config.md`: users need
the right project buckets before source tuning can feel trustworthy.

The active work in parallel is focused on reported-time phases and a Zed
collector. This task stays in the onboarding/config lane:

- no new source collector,
- no reported-time state transition,
- no invoice approval semantics,
- no migration of existing project identities.

## Backlog

### Doctor explains the next safe config step

- priority: now
- problem: `gittan doctor` can show config and source health, but users still
  need to know which safe command to run next when project config is missing,
  invalid, too broad, or under-anchored.
- user value: a user can move from "my report is empty or noisy" to the next
  low-risk action without hand-reading docs or guessing whether a command writes
  config.
- non-goals: change report classification, add new sources, rename project
  profiles, or make `doctor` write config.
- behavior:

```gherkin
Feature: Doctor routes project-config problems to safe next steps
  Users should see a non-destructive next action when project configuration is
  missing, invalid, or likely to produce poor attribution.

  Scenario: Missing project config points to setup dry-run first
    Given no projects config exists at the resolved Gittan config path
    When the user runs "gittan doctor"
    Then the output should explain that no project config was found
    And the first suggested action should be "gittan setup --dry-run"
    And the output should not imply that doctor wrote or repaired the config

  Scenario: Broad or weak project rules point to review and audit commands
    Given a projects config exists with broad tracked URLs or weak git match terms
    When the user runs "gittan doctor"
    Then the output should keep the warning row
    And the next steps should point to "gittan review" for URL mapping
    And the next steps should point to "gittan projects-audit" for rule hygiene
```

- acceptance:
  - `gittan doctor` remains read-only for project config.
  - Missing, invalid, broad, and weak-anchor states each produce one clear next
    step in user language.
  - Next-step copy uses canonical commands from `docs/product/cli-command-map.md`.
  - Existing doctor source rows and collector statuses keep their current meaning.
- validation:
  - Unit or CLI tests cover next-step selection for missing, invalid, broad, and
    weak-anchor config fixtures.
  - Run `bash scripts/cli_impact_smoke.sh` after CLI-facing edits.
  - Run `bash scripts/run_autotests.sh` before push.
- dependencies:
  - Reuse existing `core/onboarding_guidance.py` style if it remains the cleanest
    home for next-step composition.
  - Keep fixture data neutral; do not use live customer, user, or home-path names.

### Setup previews config writes before trust-sensitive changes

- priority: now
- problem: `gittan setup` is the right onboarding entry point, but config writes
  are trust-sensitive. Users should see the target path, backup behavior, and
  proposed bootstrap effect before applying changes.
- user value: a new user can trust setup because the dry run answers "what would
  change?" before any file is written.
- non-goals: introduce AI-assisted config generation, scan raw browser history,
  or replace the existing `review` mapping flow.
- behavior:

```gherkin
Feature: Setup dry-run previews project-config changes
  Setup should make project-config writes understandable before they happen.

  Scenario: Dry-run setup shows target path and proposed effect
    Given the user has no projects config
    When the user runs "gittan setup --dry-run"
    Then the output should show the resolved projects config path
    And it should summarize discovered repo/project seeds without writing them
    And it should show the next apply command

  Scenario: Invalid config is backed up before repair
    Given a projects config file exists but is invalid
    When the user chooses to repair it through setup
    Then setup should create a timestamped backup before writing a replacement
    And setup should never move or delete the only config copy without backup
```

- acceptance:
  - `--dry-run` does not create, overwrite, move, or delete
    `timelog_projects.json`.
  - Apply mode uses existing backup/write helpers before trust-sensitive writes.
  - The summary distinguishes project seeds, worklog file provisioning, and next
    suggested commands.
- validation:
  - Tests prove dry-run leaves the config path and worklog paths untouched.
  - Tests prove invalid-config repair creates a backup before replacement.
  - Run `bash scripts/cli_impact_smoke.sh` and `bash scripts/run_autotests.sh`.
- dependencies:
  - Coordinate with `docs/task-prompts/map-new-project-identity.md` before any
    billing-mode or profile-rename behavior is pulled into setup.

### Setup hands off to review without duplicating review

- priority: next
- problem: setup can create initial project buckets, while `gittan review` maps
  URL/domain evidence. Users need that sequence to feel like one path, not two
  unrelated commands.
- user value: after setup, the user knows whether to run a report, run
  interactive review, or use read-only JSON candidates for agent-assisted mapping.
- non-goals: auto-apply URL rules, replace `gittan review`, or change
  `gittan review --json` schema.
- behavior:

```gherkin
Feature: Setup-to-review handoff
  Setup should leave the next mapping action obvious without writing URL rules.

  Scenario: Setup summary suggests review when project buckets exist
    Given setup has created or confirmed at least one project bucket
    When setup finishes
    Then the summary should suggest "gittan review" for URL-to-project mapping
    And it should mention "gittan review --json" only as the read-only automation path
```

- acceptance:
  - Setup summary copy matches `docs/product/cli-command-map.md`.
  - No URL mapping is written by setup.
  - `review --json` remains read-only.
- validation:
  - CLI-output tests or snapshot-style assertions cover the summary copy.
  - Existing `review --json` read-only tests remain green.
- dependencies:
  - If command copy changes, update demo/runbook docs in the same implementation
    PR only where needed.

### Repair historically misnamed profiles

- priority: later
- problem: earlier flows could leave project profile names that are customer
  labels rather than stable repo slugs.
- user value: a user can fix old config safely after understanding the proposed
  rename and match-term changes.
- non-goals: ship in the same PR as doctor/setup guidance, or silently migrate
  profiles during report runs.
- acceptance:
  - Repair is explicit, previewed, backed up, and reversible by restoring the
    backup.
  - Coordinate with the "Later - repair misnamed profile" section in
    `docs/task-prompts/map-new-project-identity.md`.
- validation:
  - Future task prompt or implementation PR should add safe-editing tests proving
    unrelated profile fields are not overwritten.
- dependencies:
  - Wait until the active map identity work has settled.

### Optional assistant for project names

- priority: do not build yet
- problem: AI-assisted config could reduce blank-page friction, but it expands
  privacy and provider-choice scope.
- user value: eventually, users could paste a small project/customer list and get
  validated config suggestions.
- non-goals: cloud LLM by default, automatic raw trace upload, or full activity
  dump prompting.
- acceptance:
  - Future work must preserve the local-first baseline in
    `docs/security/privacy-security.md`.
  - Any cloud LLM path must be opt-in and use user-controlled credentials.
- validation:
  - Not applicable until this is promoted from "do not build yet".
- dependencies:
  - Use `docs/sources/ai-assisted-config.md` as the north star, but ship the
    non-LLM guidance slices first.

## Open decisions

- Should doctor next-step copy be a compact row in the health table, a short
  post-table list, or both?
- Should invalid-config repair live only in `setup`, or should doctor offer a
  direct "run setup" hint with the resolved path?
- Do we need a tiny generated fixture for config-quality states, or can existing
  setup/doctor test fixtures stay readable enough?

## Branch and implementation notes

- Suggested implementation branch: `task/project-config-onboarding-guidance`.
- Keep the implementation PR narrow: doctor/setup guidance and tests only.
- Avoid collector additions and reported-time changes.
- For CLI-facing edits, run `bash scripts/cli_impact_smoke.sh`.
- Before push, run `bash scripts/run_autotests.sh`.
- The implementing PR should include `Closes #197`.
