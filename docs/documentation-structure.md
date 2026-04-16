# Documentation Structure

Use this map to decide where a document belongs.

## Categories

- `docs/decisions/`
  - Stable policy and architecture decisions.
  - Examples: release policy, CI policy, privacy constraints.
- `docs/roadmap/`
  - Time-phased plans and scope boundaries.
  - Examples: v1 scope, finish plans, sequencing.
- `docs/ideas/`
  - Exploratory proposals and learning notes that are not final policy.
  - Examples: new source estimation learnings, product opportunity drafts.
- `docs/specs/`
  - Active implementation specs for work that should be built.
  - Must include goals, non-goals, acceptance criteria, and test plan.
- `docs/task-prompts/`
  - Execution prompts/checklists for implementation and validation tasks.
- `docs/incidents/`
  - Postmortems and corrective actions after concrete incidents.
- `docs/archive/`
  - Historical docs kept for context but not used as active direction.

## Fast routing rules

- If it defines a current rule -> `decisions`.
- If it proposes a future direction -> `ideas`.
- If work is approved and ready to build -> `specs`.
- If it is an implementation execution checklist/prompt -> `task-prompts`.
- If no longer current but still useful historically -> `archive`.

## Naming

- Prefer kebab-case file names in `docs/`.
- Avoid CamelCase for new docs unless keeping compatibility for externally linked legacy docs.
