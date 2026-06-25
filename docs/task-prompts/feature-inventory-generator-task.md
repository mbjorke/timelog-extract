# Feature inventory generator: code-derived docs + traceability gate

## Problem

Docs and product-backlog state drift from reality, and nothing reliably catches
it. Two concrete failures:

- **Traceability gaps go unflagged.** PRs #186/#187 (the reported-time layer)
  shipped without linking to a `docs/task-prompts/` spec with the required
  `## Traceability` block (`AGENTS.md` §223). Neither a human reviewer nor
  CodeRabbit flagged it — CodeRabbit reviews the *diff*, so a *missing* spec file
  produces no signal. The planning lived in a local `~/.claude/plans/` file,
  invisible to the repo and team.
- **No single source for "what exists."** Commands, collectors, sources, and
  config fields are spread across the code; there is no current index that maps
  each to its spec, status, and tests.

A sibling project (`akturo`) solves this with a generated
`docs/generated/feature-inventory.md` (`npm run planning:inventory`): a
code-derived raw inventory plus curated capability notes that cross-link
code ↔ docs ↔ tests ↔ backlog. We want the same for gittan, adapted to a CLI.

## Decision: a dev script, not a `gittan` command

`gittan` commands are reserved for **end users** (the product surface). Planning/
dev tooling lives in `scripts/` (alongside `check_file_lengths.py`,
`run_golden_eval.py`). So this is a standalone script, invoked in CI, never a
`gittan` subcommand.

## gittan's "features" (what the generator enumerates)

| akturo primitive | gittan equivalent | Derived from |
|---|---|---|
| App routes | **CLI commands / groups** | the Typer app in `core/cli_app.py` (registered commands) |
| API handlers | **Collectors / sources** (role, enablement) | `core/collector_registry.py` + `core/sources.py` (roles per `docs/specs/source-evidence-policy.md`) |
| Tables / enums | **Integrations & per-project config fields** (e.g. `toggl_project_id`) | `core/config.py::normalize_profile`, the sync modules |
| Product-backlog link | **Spec + `implementation_status`** | `docs/task-prompts/` + `docs/specs/` `## Traceability` blocks |

## Phased backlog

### Phase 1 — code-derived raw inventory
- priority: **now**
- scope: `scripts/generate_feature_inventory.py` writes
  `docs/generated/feature-inventory.md` with a "Generated: YYYY-MM-DD" header and:
  a summary count table; the **commands** (introspect the Typer `app` — name,
  group, help); the **collectors** (`collector_registry` — name, role, default
  enablement/reason); and the **per-project config fields**
  (`normalize_profile`). Pure read-only introspection; no network.
- acceptance: running the script regenerates the file deterministically (stable
  ordering); lists every registered command and collector; documents that the
  file is generated and points to the manual planning docs; unit test asserts the
  generator finds the known commands/collectors from a fixture/the live app.
- non-goals: lifecycle/priority/QA status (that comes from specs, Phase 2).

### Phase 2 — traceability coupling
- priority: **next**
- scope: parse the `## Traceability` blocks in `docs/task-prompts/*.md` and
  `docs/specs/*.md`; link each feature (command/collector) to its spec +
  `implementation_status`. Curated capability notes (hand-written) sit above the
  auto rows, mirroring akturo's "Curated capabilities".
- acceptance: each command/collector shows its linked spec + status, or
  "(no spec)" when none references it; a feature→spec map is emitted.

### Phase 3 — `--check` mode + CI gate
- priority: **next**
- scope: `scripts/generate_feature_inventory.py --check` exits non-zero when a
  command/collector has **no linked spec**, or when the generated file is stale
  (regenerate-and-diff). Wire into `scripts/run_autotests.sh` / CI.
- decision needed: **hard gate vs advisory** (fail CI vs warn). See Open decisions.
- acceptance: a new command with no spec reference fails `--check`; a stale
  inventory file fails `--check`; both pass after a spec link / regeneration.

### Ongoing — curated capability notes (manual layer)
- priority: **later** (continuous)
- hand-written cross-cutting flow notes (e.g. "Toggl posting", "reported-time
  layer") with command · code · source-role · config · spec(+status) · tests,
  like akturo's curated capabilities.

## Behavior Contract

```gherkin
Feature: Code-derived feature inventory with a traceability gate

  Scenario: The inventory lists a newly added command
    Given a new "gittan reported" command group is registered
    When the inventory generator runs
    Then the generated file lists "reported" with its subcommands and help

  Scenario: A feature without a spec is flagged
    Given a command/collector that no docs/task-prompts spec references
    When the generator runs with --check
    Then it reports the feature as "(no spec)"
    And --check exits non-zero (per the chosen gate strictness)

  Scenario: A stale inventory file is caught
    Given the code changed but docs/generated/feature-inventory.md was not regenerated
    When --check runs in CI
    Then it fails and tells the developer to rerun the generator
```

## Acceptance criteria (overall)

- `scripts/generate_feature_inventory.py` produces a deterministic
  `docs/generated/feature-inventory.md` from code introspection (no manual list
  to maintain).
- Each command/collector links to its spec + `implementation_status`, or is
  flagged as un-specced.
- `--check` catches un-specced features and stale output; wired into CI.
- No `gittan` end-user command is added.
- Tests cover generation + the `--check` failure/clean paths; no file > 500 lines.

## Open decisions

- **Gate strictness:** is `--check` a **hard CI failure** or advisory warning for
  the un-specced-feature case? (Stale-file check should be hard regardless.)
- **Spec linkage key:** how does a spec declare which command/collector it
  covers — an explicit `covers:` field in the Traceability block, or name
  matching? An explicit field is more robust.
- Where curated notes live (in the generated file's top section vs a separate
  hand-maintained doc the generator includes).

## Follow-up (separate, surfaced by this work)

Backfill the reported-time layer's traceability: add
`docs/task-prompts/reported-time-layer-task.md` (phases 1–5) with a `## Traceability`
block linking #186/#187, and update `docs/specs/scheduled-reported-time-bridge.md`
delivery phases. This is what the generator's `--check` would have demanded.

## Branch

`task/feature-inventory-generator` from latest `main`.

## Traceability

- story_id: GH-TBD (feature-inventory generator)
- spec_status: draft
- implementation_status: not built
- created_at: 2026-06-25
- last_updated_at: 2026-06-25
- implementation.pr: pending
- implementation.branch: task/feature-inventory-generator
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- related:
  - model: `~/Workspace/Project/akturo/docs/generated/feature-inventory.md`
  - policy: `AGENTS.md` §223 (task spec traceability); `docs/task-prompts/task-traceability-template.md`
  - surfaced by: reported-time layer PRs #186 / #187 shipping without a linked spec
- changelog:
  - 2026-06-25: Initial draft. Shaped from the docs/backlog-freshness discussion
    after #186/#187 shipped without a traceable spec link; modeled on akturo's
    generated feature inventory; scoped as a dev script (not a gittan command).
