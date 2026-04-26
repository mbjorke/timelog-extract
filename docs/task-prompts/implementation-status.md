# Task prompts implementation status

Status: active tracker  
Last updated: 2026-04-25

## Purpose

Track prompt execution reality, not only intended state in old prompt metadata.

## Status scale

- `not built`: prompt scope has not been materially implemented.
- `in progress`: implementation is underway but not complete.
- `built`: primary prompt scope implemented.
- `verified`: implemented and validated with durable evidence.

## Current matrix


| Task prompt                                                | Current status | Evidence / notes                                                                                                                                    |
| ---------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/task-prompts/copilot-cli-source-task.md`             | `built`        | Copilot collector and wiring exist in `collectors/copilot_cli.py`, `core/collector_registry.py`, with tests in `tests/test_copilot_cli_collect.py`. |
| `docs/task-prompts/live-terminal-sandbox-demo-task.md`     | `in progress`  | Allowlist contract + deterministic sandbox behavior are implemented, but full hardening/production-grade scope remains open.                        |
| `docs/task-prompts/ab-rule-suggestions-task.md`            | `built`        | Suggest/apply + integrated review paths are present; task prompt reflects built status.                                                             |
| `docs/task-prompts/ab-rule-suggestions-ux-task.md`         | `not built`    | Still draft next-pass UX task; no explicit completion evidence in prompt metadata.                                                                  |
| `docs/task-prompts/agent-inline-cli-ux-validation-task.md` | `not built`    | Approved task prompt, but traceability still says not built.                                                                                        |
| `docs/task-prompts/dev-main-alignment-handoff.md`          | `not built`    | Operational handoff doc; execution is runbook-driven and out-of-band.                                                                               |
| `docs/task-prompts/task-traceability-template.md`          | `not built`    | Template file, not an implementation task; excluded from execution tracking decisions.                                                              |


## Update routine

When prompt implementation changes:

1. Update the prompt traceability fields.
2. Update this matrix row in the same PR.
3. Add at least one concrete evidence anchor (code path, test, PR, or runbook validation).

