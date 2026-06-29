# Feature inventory generator: code-derived docs + traceability gate

## Problem

Docs and product-backlog state drift from reality, and nothing reliably catches
it. Two concrete failures:

- **Traceability gaps go unflagged.** PRs #186/#187 (the reported-time layer)
  shipped without linking to a `docs/task-prompts/` spec with the required
  `## Traceability` block (`AGENTS.md` §223). Neither a human reviewer nor
  CodeRabbit flagged it — CodeRabbit reviews the *diff*, so a *missing* spec file
  produces no signal. The planning lived in a local plan-mode file,
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
- priority: **built** — this PR
- scope: `scripts/generate_feature_inventory.py` writes
  `docs/generated/feature-inventory.md` with a "do not edit by hand" banner and:
  a summary count table; the **commands** (introspect the Typer `app` — name,
  group, help); the **collectors** (parsed from `collector_registry` — name +
  unit_label); and the **per-project config fields** (`normalize_profile`). Pure
  read-only introspection; no network. A lightweight `--check` (regenerate-and-diff
  staleness) ships here too; the un-specced-feature gate is Phase 2-3.
- decision: the banner carries **no date** — a "Generated: YYYY-MM-DD" line would
  break the deterministic regenerate-and-diff that `--check` relies on, so the
  generated marker is a plain do-not-edit banner instead.
- acceptance: running the script regenerates the file deterministically (stable
  ordering, no timestamp); lists every registered command and collector; documents
  that the file is generated and points to the manual planning docs; a unit test
  asserts the generator finds the known commands/collectors/config fields and that
  the committed file is up to date (the in-CI staleness guard).
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
- scope: extend `--check` so it also reports a command/collector with **no linked
  spec** (Phase 2 data). Per the resolved gate decision below: the **stale-file**
  check is a **hard** failure (already enforced by the Phase 1 unit test in CI);
  the **un-specced-feature** check is **advisory** (warn + list) by default and
  **hard only with `--strict`**, so the existing un-specced surface doesn't block
  CI until it is specced. Optionally also wire the script's `--check` into
  `scripts/run_autotests.sh` alongside the test.
- acceptance: a new command with no spec reference fails `--check --strict`; a stale
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

## Decisions

- **Gate strictness (resolved):** the **stale-file** check is a **hard** failure;
  the **un-specced-feature** check is **advisory** by default and hard only with
  `--strict`, so the existing un-specced surface does not block CI until specced.

## Open decisions

- **Spec linkage key:** how does a spec declare which command/collector it
  covers — an explicit `covers:` field in the Traceability block, or name
  matching? An explicit field is more robust. (Phase 2.)
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

- story_id: GH-199
- spec_status: draft
- implementation_status: in progress — Phase 1 (code-derived inventory + `--check`
  staleness) built this PR; Phases 2-3 (spec linkage + un-specced gate) not built
- created_at: 2026-06-25
- last_updated_at: 2026-06-26
- implementation.pr: this PR (Phase 1)
- implementation.branch: task/feature-inventory-generator
- implementation.commits: []
- validation.evidence: `scripts/generate_feature_inventory.py`,
  `tests/test_feature_inventory.py`, `docs/generated/feature-inventory.md`
- validation.decision: GO for Phase 1; Phases 2-3 pending
- related:
  - model: the sibling `akturo` project's generated `docs/generated/feature-inventory.md`
  - policy: `AGENTS.md` §223 (task spec traceability); `docs/task-prompts/task-traceability-template.md`
  - surfaced by: reported-time layer PRs #186 / #187 shipping without a linked spec
- changelog:
  - 2026-06-25: Initial draft. Shaped from the docs/backlog-freshness discussion
    after #186/#187 shipped without a traceable spec link; modeled on akturo's
    generated feature inventory; scoped as a dev script (not a gittan command).
  - 2026-06-26: Phase 1 built — `scripts/generate_feature_inventory.py` +
    `docs/generated/feature-inventory.md` + tests. Resolved the `--check` gate
    decision (stale=hard, un-specced=advisory/`--strict`); recorded the no-date
    banner decision (deterministic `--check`); set `story_id: GH-199`; removed
    local home paths from this spec and the product-owner skill (the four
    CodeRabbit threads left unresolved on #188).
