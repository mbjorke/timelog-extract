# Task Story: Add GitHub Copilot CLI As A Source

Use this task story to implement first-class source support for GitHub Copilot CLI
activity in Gittan with safe defaults and clear diagnostics.

## Traceability

- story_id: `GH-123`
- spec_status: `draft`
- implementation_status: `not built`
- created_at: `2026-04-15`
- last_updated_at: `2026-04-15`
- implementation.pr: `pending`
- implementation.branch: `pending`
- implementation.commits: `[]`
- validation.evidence: `pending`
- validation.decision: `NO-GO`
- changelog:
  - `2026-04-15: Initial task story created.`
  - `2026-04-15: Added mandatory traceability metadata and dev branch-flow defaults.`

## Why this matters

Users ask whether Gittan supports Copilot CLI directly. Today, Copilot CLI usage
may appear only indirectly via terminal/context traces. This task adds explicit
source detection so Copilot work is visible, measurable, and classifiable.

## Goal

Add a dedicated Copilot CLI collector and source wiring so Copilot CLI sessions
can be included in reports, source summaries, and diagnostics.

## Scope (v1)

1. Source detection for Copilot CLI local artifacts (log/events footprints).
2. Collector integration into pipeline/runtime/registry.
3. `gittan doctor` visibility for Copilot CLI source health.
4. Source naming/order integration in output (`source-summary`, legends).
5. Tests for path detection and collector parsing behavior.

## Non-goals (v1)

- No network calls to GitHub APIs for Copilot usage.
- No cloud dependency; local-first only.
- No billing heuristics specific to Copilot beyond normal project classification.

## Branch and workflow defaults

- Branch from latest `main` using a short-lived `task/<short-scope>` branch.
- Keep PR scope focused on source support only.
- Do not include unrelated docs cleanup in this task.

## Expected user-facing behavior

- `gittan doctor` shows Copilot CLI status (`found`/`not found`).
- `gittan report --today --source-summary` can show Copilot CLI events.
- Copilot CLI events participate in normal project classification rules.

## Implementation hints

- Follow existing source patterns (`Claude Code CLI`, `Cursor`, etc.).
- Keep collector resilient to missing files/permissions.
- Normalize event detail to include enough context for classification without
  leaking unnecessary raw noise.

## Safety constraints

- Never fail the whole report if Copilot artifacts are missing/unreadable.
- Handle parse errors defensively; mark collector status instead of crashing.
- Respect existing source toggles and exclusion behavior.

## Tests required

- Unit tests for:
  - Copilot root/path discovery
  - collector parsing of representative records
  - graceful handling when artifacts are absent/corrupt
- Regression check:
  - `./scripts/run_autotests.sh` passes

## Acceptance criteria

- Copilot CLI appears as a distinct source in runtime/source summary.
- Doctor command reports Copilot CLI availability.
- No regressions in existing collectors and report flows.
- Changelog `Unreleased` includes Copilot CLI source support note.

## PR output checklist

When task implementation is done, include:

1. Summary of source integration points changed
2. Example `doctor` output showing Copilot status
3. Example `source-summary` output including Copilot
4. Test evidence and known limitations
