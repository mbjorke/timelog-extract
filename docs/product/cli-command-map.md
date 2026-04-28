# CLI command map (post-pages.dev)

Status: active guidance

## Why this exists

The public pages copy and the real CLI must describe the same product.
This map is the source of truth for command language in docs, demos, and landing copy.

## Decision

Keep the current CLI command set as the canonical product contract (Option A).
Do not make breaking renames now. If we later want `capture/review` wording, add aliases first.

## Command map

| Truth layer | User intent | Canonical CLI command | Notes |
| --- | --- | --- | --- |
| Observed evidence | Verify local setup and source health | `gittan doctor` | Fast setup visibility and next steps when sources are missing. |
| Observed evidence | Build an evidence report for a date range | `gittan report --today --source-summary` | Default reporting shape for demos and onboarding. |
| Observed evidence | Inspect all event-level details for a project/date | `gittan search --today --project "<name>"` | Search is the audit/debug lens (`all_events=True` path). |
| Classified candidates | Manually curate uncategorized clusters (advanced) | `gittan review --today` | Advanced interactive loop; powerful but usually not the first onboarding step. |
| Classified candidates | Generate read-only mapping suggestions | `gittan triage --json` | Suggestion/evidence-first flow before config writes. |
| Classified candidates | Apply accepted triage suggestions | `gittan triage-apply --yes` | Human-approved write step after review. |
| Approved summary | Quick total/status check | `gittan status --today --additive` | High-level summary across projects/sessions. |
| Onboarding | Run setup wizard | `gittan setup` | One-click default; `--interactive` and `--dry-run` available. |

## Demo subset (live terminal sandbox)

The live terminal demo is intentionally a safe subset of CLI behavior:

- `gittan doctor`
- `gittan setup`
- `gittan setup --dry-run`
- `gittan status`
- `gittan report`
- `gittan report --today --source-summary`
- `gittan report --today --format json`
- `gittan report --today --invoice-pdf`
- `help`
- `clear`

Reference implementation: `core/live_terminal/contract.py`.

## Copy rules

- Do not market unimplemented commands (for example `gittan capture`) as real CLI behavior.
- For onboarding/default flow text, prefer this setup sequence:
  - Step 1: Global Timelog Setup
  - Step 2: Project Bootstrap
  - Step 3: Project Mapping
  - Step 4: Doctor Check
  - Step 5: Triage Review (optional)
- After setup, prefer interactive flow over flag-heavy instructions:
  - `gittan triage --json` (read-only plan; timeframe picker when date flags are omitted)
  - `gittan triage-apply --interactive-review` after explicit review (use `--yes` only after confirming the plan)
  - Workflow contract reference: `docs/runbooks/gittan-triage-agents.md`
- Position `gittan review` as advanced/manual cleanup, not the default first-run path.
- If we add future aliases, document them as additive language, not replacements, until migration is complete.
