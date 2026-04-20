---
description: Deep review for gittan triage, CLI agent flows, and JSON plan output
---

# Ultrareview (gittan / triage)

Use this when reviewing **triage**, **gap mapping**, or **agent-facing CLI** changes.

## Before you judge the diff

1. Read **`docs/runbooks/gittan-triage-agents.md`** (JSON contract, `--json` vs `--yes`, privacy).
2. Confirm **`gittan triage --json`** stays **read-only** (no config writes).
3. Prefer **site-first / `tracked_urls`** as the primary signal; treat **`match_terms`** as secondary unless the change explicitly documents otherwise.

## Review checklist

- **Import safety**: `core.report_service` must not circular-import via `cli_triage` at module load (lazy import inside the command handler is OK).
- **Automation path**: `--yes` must not throw on unknown project names; skip with a clear reason (same as interactive safety).
- **Tests**: helpers (`select_triage_days`, `resolve_target_project_name`, plan JSON) have unit coverage; subprocess import smoke still passes.
- **PII**: JSON output omits Chrome page titles; stderr noise from collectors is acceptable for humans but noted for CI/agents.

## Optional: validate behavior

From repo root with a throwaway date range:

`python3 timelog_extract.py triage --json --max-days 1 --from 2000-01-01 --to 2000-01-02`

Expect a single JSON object on stdout and exit code `0`.

## Creativity / product

Use this pass for **UX copy**, **discoverability**, and **future timeline / Jira-style views** — not for expanding scope in the same PR unless requested.
