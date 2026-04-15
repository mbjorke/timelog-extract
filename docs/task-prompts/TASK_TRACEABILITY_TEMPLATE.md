# Task Traceability Template

Use this block in every task spec/prompt under `docs/task-prompts/`.

## Traceability

- story_id: `GH-123` (or `JIRA-123`)
- spec_status: `draft | approved | superseded`
- implementation_status: `not built | in progress | built | verified`
- created_at: `YYYY-MM-DD`
- last_updated_at: `YYYY-MM-DD`
- implementation.pr: `<url-or-pr-ref>`
- implementation.branch: `<branch-name>`
- implementation.commits: `[<sha1>, <sha2>]`
- validation.evidence: `<path-or-url>`
- validation.decision: `GO | conditional GO | NO-GO`
- changelog:
  - `YYYY-MM-DD: Initial draft created.`
  - `YYYY-MM-DD: <requirement/gate/threshold change note>.`

## Example (copy and edit)

- story_id: GH-123
- spec_status: draft
- implementation_status: not built
- created_at: 2026-04-15
- last_updated_at: 2026-04-15
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - 2026-04-15: Initial draft created.

## Usage notes

- Do not leave implementation state implicit.
- If no implementation exists yet, set `implementation_status: not built`.
- Every requirement/gate/threshold change must:
  - update `last_updated_at`
  - append one line in `changelog`.
