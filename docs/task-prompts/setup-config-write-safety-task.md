# Setup config write safety

**Critical follow-up to GH-197.** GH-197 improved onboarding *guidance* (doctor/setup/review
next steps, dry-run preview, backup before *invalid-config repair*). A real incident on
2026-06-26 showed that **`gittan setup` apply can still merge-write over a valid
`timelog_projects.json` without a loud warning or backup**, which can destroy hours of
tuned `match_terms`, `tracked_urls`, and profile fields.

This task is **trust-critical** and should ship before further onboarding UX polish.

## Traceability

- story_id: GH-211
- spec_status: approved
- implementation_status: in progress
- last_updated_at: 2026-06-29
- changelog:
  - 2026-06-29: Initial spec after maintainer incident — valid config overwritten during GH-197 setup testing; backup from 2026-06-25 retained 39 projects while apply path rewrote config without adequate warning.
  - 2026-06-29: Slices A/B implemented — write gate, --bootstrap-repos, backup before merge-write, guidance copy.

## Incident context

- Maintainer backup `timelog_projects.backup.20260625-174125.json` (39 projects, valid JSON).
- Apply/setup on 2026-06-26 produced `timelog_projects.backup-20260626-201749.json` (invalid-config
  repair naming pattern) and a smaller rewritten config (~34 projects, ~13 KB).
- User report: no clear warning that bootstrap **merge** would damage an existing tuned config.
- Related: [`docs/incidents/2026-04-13-project-config-backup-gap.md`](../incidents/2026-04-13-project-config-backup-gap.md)
- Adjacent shipped work: GH-197 / [`project-config-onboarding-guidance-task.md`](project-config-onboarding-guidance-task.md)

## Non-goals (locked)

- No changes to reported-time computation, sync, or store semantics.
- No new or modified source collectors.
- No changes to `gittan review --json` schema or write behavior.
- No profile rename/repair automation (stay deferred from GH-197).
- No AI-assisted config generation.
- No export/import command in this task (separate **next** item).

## Related material

- Code: `core/setup_projects_config_bootstrap.py` (`ensure_projects_config`),
  `core/global_timelog_setup_lib.py`, `core/onboarding_guidance.py`,
  `core/config.py` (`backup_projects_config_if_exists`)
- Tests: `tests/test_setup_projects_config.py`, `tests/test_onboarding_next_steps.py`
- Runbook: [`docs/runbooks/beta-onboarding-config.md`](../runbooks/beta-onboarding-config.md)
- Command map: [`docs/product/cli-command-map.md`](../product/cli-command-map.md)

## Why this is **now**

Product bet #3 in [`docs/ideas/opportunities.md`](../ideas/opportunities.md): simplify project
configuration. That fails if the primary onboarding command can silently damage the user's
only copy of critical config. GH-197 told users *where to go*; this task makes setup
**safe by default** for existing users.

## Implementation slices

Ship on branch `task/setup-config-write-safety` as **two implementation commits** (A then B).

| Slice | Scope | Status |
| --- | --- | --- |
| **A — Write gate + backup** | Valid config: no merge-write unless explicit opt-in; backup before any setup config write; stronger apply/dry-run copy | **built** |
| **B — Doctor/guidance + tests** | Doctor must not suggest destructive setup when config PASS; tests + CLI smoke | **built** |

### Slice A — behavior contract (write gate)

```gherkin
Feature: Setup does not merge-write valid project config by default
  Existing tuned config is critical local data; apply must be opt-in and backed up.

  Scenario: Valid config exists — default setup is non-destructive
    Given timelog_projects.json exists at the resolved Gittan config path
    And the file loads as valid project config with at least one project
    When the user runs "gittan setup" without an explicit bootstrap-merge flag
    Then setup must not write timelog_projects.json
    And setup must explain that repo bootstrap merge was skipped to protect existing config
    And setup should suggest "gittan review", "gittan projects-audit", or "gittan projects" instead

  Scenario: Explicit bootstrap merge requires backup and confirmation
    Given timelog_projects.json exists and is valid
    When the user runs setup with an explicit bootstrap-merge flag (e.g. "--bootstrap-repos")
    And confirms the merge (or passes a dedicated non-interactive confirm flag)
    Then setup creates a timestamped backup via backup_projects_config_if_exists before writing
    And the summary shows discovered, added, updated, and skipped counts
    And the output includes an explicit warning that match_terms and tracked_urls may change

  Scenario: Invalid config repair keeps GH-197 backup behavior
    Given timelog_projects.json exists but is not valid project config
    When the user confirms repair through setup
    Then setup creates a timestamped backup before replacement
    And the user sees the backup path in the summary

  Scenario: Dry-run never writes
    Given any config state
    When the user runs "gittan setup --dry-run"
    Then no config or worklog files are created, overwritten, moved, or deleted
    And dry-run copy states whether apply would merge, skip, or repair
```

**Suggested CLI surface (decision — implementer picks one, document in command map):**

- Preferred: **`--bootstrap-repos`** on `gittan setup` to opt into merge-write when config
  already valid. Default apply = hooks/env/mapping steps only; project bootstrap merge skipped.
- `--yes` must **not** bypass the write gate for valid existing config (only non-destructive steps).

### Slice B — behavior contract (guidance)

```gherkin
Feature: Doctor and setup next steps do not steer users into destructive apply
  Guidance must match write-safety defaults from slice A.

  Scenario: Doctor with healthy config does not suggest plain setup apply
    Given timelog_projects.json exists and validates
    And gittan doctor reports project config PASS
    When the user reads doctor next steps
    Then the steps must not say "run gittan setup" as the primary fix
    And steps should point to review, projects-audit, or report as appropriate

  Scenario: Dry-run next steps mention bootstrap flag when merge is skipped
    Given valid existing config
    When the user runs "gittan setup --dry-run"
    Then next steps explain that apply will not merge repos unless "--bootstrap-repos" is used
```

## Backlog

### Valid config write gate (default: no merge-write)

- priority: **now**
- problem: `ensure_projects_config` always merge-writes on apply when config is valid,
  with no backup and no explicit user consent for overwriting tuned profiles.
- user value: experienced users can run setup/doctor without losing critical config.
- non-goals: change merge algorithm semantics beyond write gating; auto-repair profiles.
- acceptance:
  - Valid config + default `gittan setup` → config file unchanged (mtime + content hash).
  - Explicit bootstrap flag + confirm → backup then merge-write.
  - `--yes` cannot trigger merge-write on valid config without the bootstrap flag.
  - Invalid/missing config paths unchanged from GH-197 except copy improvements.
- validation:
  - Extend `tests/test_setup_projects_config.py` (valid config untouched, backup on merge,
    dry-run untouched).
  - Update `tests/test_onboarding_next_steps.py` for doctor/setup copy.
  - `bash scripts/cli_impact_smoke.sh` and `bash scripts/run_autotests.sh`.
- dependencies: reuse `backup_projects_config_if_exists`; coordinate flag name with CLI map.

### Loud apply/dry-run warnings

- priority: **now**
- problem: green "Saved merged project config" and neutral `added/updated` counts do not
  communicate risk to users with existing tuned config.
- user value: user understands *before* apply whether their config will change.
- acceptance:
  - Apply path that will write shows yellow/red warning when projects exist or counts > 0.
  - Dry-run states skip vs merge vs repair explicitly.
  - Setup summary never implies success when merge was skipped due to write gate.
- validation: CLI output tests or recorded console assertions in existing test modules.

### Doctor guidance alignment

- priority: **now** (slice B)
- problem: `build_doctor_next_steps` / `build_setup_next_steps` can still read as "run setup"
  when config is already healthy.
- acceptance: PASS config → no plain setup apply in primary next steps; bootstrap flag documented.
- validation: unit tests on `build_doctor_next_steps` / `build_setup_next_steps`.

### Export/import user config

- priority: **next**
- problem: users need a supported recovery path beyond ad-hoc backup files.
- dependencies: incident follow-up from 2026-04-13; out of scope for this task.

## Open decisions

- Flag name: `--bootstrap-repos` vs `--merge-repos` (prefer former; align with command map).
- Should skipped merge still run repo **scan in dry-run only** for preview? (Recommended: yes in dry-run, no write.)
- Interactive confirm text vs Rich panel — match terminal style guide.

## Branch and implementation notes

- Branch: `task/setup-config-write-safety`
- PR title (English): `fix(setup): gate config merge-write behind explicit opt-in (GH-211)`
- PR body must include: `Closes #211`, link this spec, note incident 2026-06-26.
- Run `bash scripts/cli_impact_smoke.sh` after CLI-facing edits; full suite before push.
