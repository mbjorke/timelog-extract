# Task Prompt: A/B Suggestions For Uncategorized Rules (0.2.8)

Use this prompt to implement a v1 task with minimal back-and-forth.
Default behavior and decisions are defined below so the agent can proceed without
asking clarifying questions unless there is a blocker.

## Traceability

- story_id: `GH-123`
- spec_status: `approved`
- implementation_status: `built`
- created_at: `2026-04-15`
- last_updated_at: `2026-04-15`
- implementation.pr: `pending`
- implementation.branch: `pending`
- implementation.commits: `[]`
- validation.evidence: `pending`
- validation.decision: `conditional GO`
- changelog:
  - `2026-04-15: Initial task prompt created.`
  - `2026-04-15: Added mandatory traceability metadata and updated branch defaults.`

## Goal

Add an assistant flow that proposes project-config rules from uncategorized events:

- Option A: `safe` (higher precision, fewer rules)
- Option B: `broad` (higher recall, more rules)

The user must explicitly confirm before any write to `timelog_projects.json`.

## Branch and mode defaults

- Work on a short-lived `task/<short-scope>` branch from latest `dev`.
- Keep changes incremental and reviewable.
- If uncertain, prefer extending existing modules over adding many new files.
- Do not break existing `gittan review --uncategorized`.

## CLI contract (v1 defaults)

Implement at least one of these paths (both preferred):

1. Split commands:
   - `gittan suggest-rules --project "<name>" --today`
   - `gittan apply-suggestions --option A --confirm`
2. Integrated path:
   - `gittan review --uncategorized --ab-suggestions`

If only one path is feasible in v1, implement integrated `review` path first.

## Behavior requirements

- Source suggestions from uncategorized clusters in selected timeframe.
- Show impact preview before apply:
  - estimated `+events`
  - estimated `+hours`
  - estimated `-uncategorized`
- Show sample matches per candidate rule (at least 1-3 samples).
- Require explicit confirmation before apply (`--confirm` or interactive accept).
- Create timestamped backup before write.
- Write via existing safe config path (`save_projects_config_payload`).

## Heuristic defaults (no extra product questions)

- A (`safe`):
  - stronger domain/URL anchors
  - repeated terms with lower cross-project ambiguity
  - fewer rules
- B (`broad`):
  - includes A plus medium-confidence terms
  - may include route/feature tokens (e.g. checkout/pricing/subscription)

Use existing clustering helpers and keep heuristics transparent in output.

## Safety constraints

- Never move/delete `timelog_projects.json`.
- Never write without explicit user approval.
- If suggestion quality is too weak, show "no safe suggestions" instead of guessing.

## Acceptance criteria

- New command/help text is visible and understandable.
- A/B suggestions appear for real uncategorized data.
- Preview shows `+events/+hours/-uncategorized`.
- Apply path creates backup and writes only selected option.
- Existing review workflow still works without `--ab-suggestions`.
- Unit tests cover:
  - A vs B split
  - preview impact math
  - backup + apply flow
- `./scripts/run_autotests.sh` passes.
- `CHANGELOG.md` Unreleased includes this feature.

## Task output format for PR notes

Provide:

1. Summary bullets (what changed and why)
2. Example terminal output for A/B preview
3. Test evidence (unit + autotests)
4. Known limitations (if any) and follow-up scope

