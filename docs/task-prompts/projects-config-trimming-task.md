# Task Prompt: Manual projects-config trimming (audit + optional apply)

Read-only usage statistics for `match_terms` / `tracked_urls`, then optional
explicit removal with backup — complements `projects-lint` (structural overlap)
and triage flows that require Screen Time gap days.

## Traceability

- story_id: GH-123
- spec_status: draft
- implementation_status: not built
- created_at: 2026-05-02
- last_updated_at: 2026-05-02
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - 2026-05-02: Initial draft from planning thread (phased audit + manual apply).

Replace `story_id` with a real GitHub issue reference when one exists.

## Goal

1. **Phase 1 — Audit**: New CLI command (name TBD, e.g. `gittan projects-audit`)
   reports per-project hit counts for each `match_term` and `tracked_urls`
   fragment over a user-selected date window, using the same event collection
   path as reports. Optional `--json` stdout schema v1 (distinct from
   `gittan triage --json`). Clearly document that zero hits means “in this
   window”, not “safe to delete forever”.

2. **Phase 2 — Trim**: Apply removals only with explicit human/agent approval:
   `--dry-run`, timestamped backup via existing config helpers, optional
   decisions JSON (pattern after `triage-apply`), then re-run `projects-lint`.

## Non-goals

- Automatic bulk deletion without confirmation.
- Changing core classification weights (`classify_project`) beyond what’s
  needed for “did this rule participate in a match” accounting (if that
  definition is chosen).

## Design decisions (lock in implementation)

- **Hit definition**: Prefer documenting whether counts mean “substring present in
  event text” vs “winning project for that event” — pick one v1 rule and test
  it.
- **Privacy**: JSON mode should aggregate counts; avoid echoing raw `detail`
  fields unless a debug flag is explicitly added later.
- **File size**: Stay under the 500-line Python file limit; split modules if
  needed.

## Branch and validation

- Branch: `task/projects-config-trimming` (or shorter) from latest `main`.
- Tests: synthetic fixtures only; no real customer names or home paths in
  committed data.
- Gate: `bash scripts/cli_impact_smoke.sh` for CLI changes; `bash scripts/run_autotests.sh` before push.

## References

- `core/projects_lint.py` — overlap / risk warnings (orthogonal to usage).
- `core/config.py` — `backup_projects_config_if_exists`, `save_projects_config_payload`.
- `docs/runbooks/gittan-triage-agents.md` — pattern for read-only vs apply JSON.
