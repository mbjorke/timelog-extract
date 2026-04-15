# RC Prompt: Agent Inline CLI UX Validation

Use this prompt to implement the highest-priority RC candidate from today's docs:
make agent-driven development validate CLI UX continuously via inline command
smoke checks, not only at PR end.

## Goal

When CLI-related code changes, the agent automatically runs a minimal local smoke
loop and reports expected vs actual UX outcomes in its response.

## Priority

This RC is priority #1.

## Branch and mode defaults

- Branch: create a short-lived feature branch from latest `main`.
- Mode: implementation-first, minimal ceremony.
- Keep scope small and incremental; avoid broad refactors.

## Inputs / source docs

- `docs/decisions/agent-inline-cli-ux-validation.md`
- `AGENTS.md` (local data safety and release/branch policy)

## Required behavior (v1)

1. Detect CLI-impacting edits (commands, flags, command output copy, onboarding
   next steps, report formatting, diagnostics output).
2. Run this inline smoke loop after meaningful edits:
   - `python3 -m timelog_extract -V`
   - `python3 -m timelog_extract report --today --source-summary`
   - plus at least one command specific to the edited feature path.
3. Report a short UX verdict in agent output:
   - expected behavior
   - observed behavior
   - mismatch/blocker (if any)
4. If a smoke command fails, stop and surface the blocker clearly (no guessing).

## Safety and guardrails

- No destructive setup tricks (`mv`/`rm` on `timelog_projects.json` etc.).
- Use explicit confirmation paths for write commands.
- Keep runtime checks fast; avoid heavy loops on every tiny edit.
- Never commit local-only artifacts (`TIMELOG.md`, `private/`, temp state files).

## Implementation suggestions

- Add a small helper module for inline smoke orchestration, e.g.
  `core/cli_inline_smoke.py`, or extend existing CLI helper surfaces if cleaner.
- Keep command execution wrapper pure/testable where possible.
- Add a compact result model (`ok`, `command`, `summary`, `error`).

## Tests (required)

- Unit tests for:
  - smoke command plan composition based on changed feature scope
  - success/failure result formatting
  - fail-fast behavior when one command errors
- Keep existing test suite green:
  - `./scripts/run_autotests.sh`

## Acceptance criteria

- Inline smoke checks run for CLI-impacting changes.
- Agent output includes concise UX validation summary.
- Failures are explicit and actionable.
- No regressions in existing CLI flows.
- Docs updated minimally if command contract changed.

## RC output format

When done, provide:

1. What triggers inline smoke checks
2. Commands executed and why
3. Example success and failure summaries
4. Test evidence (`unittest` + `./scripts/run_autotests.sh`)
