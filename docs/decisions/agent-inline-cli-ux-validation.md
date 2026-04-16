# Agent Inline CLI UX Validation

Status: Active routine  
Cadence: During active feature development  
Owner: Active agent

## Purpose

Reduce late surprises by validating CLI behavior and wording while changes are still
small. The agent should run `gittan` commands inline during implementation, not only
at PR-final test time.

## Decision

For CLI-impacting work, the agent must execute a minimal inline smoke loop after
meaningful edits and before claiming the change is done.

## Default inline smoke loop

1. **Version/runtime sanity**
   - `python3 -m timelog_extract -V`
2. **Core report UX sanity**
   - `python3 -m timelog_extract report --today --source-summary`
3. **Feature-targeted command(s)**
   - Run the command path touched by the change.
   - Example for suggestions flow:
     - `python3 -m timelog_extract suggest-rules --project "Time Log Genius" --today`
4. **Result note in agent output**
   - Report expected vs actual behavior in 1-3 lines.
   - If blocked, report exact blocker and stop guessing.

## One-command bundle (repo root)

Agents can run the same loop mechanically:

```bash
bash scripts/cli_impact_smoke.sh
```

Override entrypoint if needed: `TIMOLOG_ENTRY=timelog_extract.py PYTHON=python3.12 bash scripts/cli_impact_smoke.sh`.

## Guardrails

- Prefer non-destructive commands in routine smoke checks.
- If write paths are involved, use explicit confirmation and existing backup behavior.
- Do not mutate or move `timelog_projects.json` as part of test setup.
- Keep checks fast; use the smallest command set that validates changed UX.

## Exit criteria for "done"

Work is not considered done until:

- inline smoke loop has run for the changed CLI path,
- observed UX is reported,
- and blocking mismatches are either fixed or explicitly escalated.
