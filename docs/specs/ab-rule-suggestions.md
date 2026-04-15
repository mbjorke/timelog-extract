# Spec: A/B Rule Suggestions For Uncategorized Review

Status: Draft (v1)
Owner: Maintainer + AI agents

## Problem

Manual rule tuning in `timelog_projects.json` is slow and error-prone. Users need
AI-assisted suggestions with explicit approval before writing config changes.

## Goals

- Generate two suggestion sets from uncategorized activity:
  - Option A (`safe`): high precision, fewer rules.
  - Option B (`broad`): higher recall, more rules.
- Show projected impact before applying:
  - `+events`, `+hours`, `-uncategorized`.
- Keep user in control: no writes without explicit confirmation.

## Non-goals (v1)

- Fully automated rule application.
- Remote/cloud AI dependency required for base behavior.
- Perfect classification confidence scoring.

## Proposed CLI

Primary:

- `gittan suggest-rules --project "Time Log Genius" --today`
- `gittan apply-suggestions --option A --confirm`

Alternative integrated path:

- `gittan review --uncategorized --ab-suggestions`

## Input data

- Existing report events for chosen timeframe with `include_uncategorized=true`.
- Existing `timelog_projects.json`.
- Cluster helpers from `core/uncategorized_review.py`.

## Suggestion model (v1 heuristic)

For target project:

- `tracked_urls` candidates:
  - domains/URLs recurring in uncategorized cluster samples.
  - prioritize deterministic identifiers (project IDs, stable hosts).
- `match_terms` candidates:
  - route names, feature names, known product terms (e.g. `checkoutsuccess`).

Option A (`safe`) keeps only high-confidence candidates:

- appears in multiple events
- low overlap with other existing projects
- URL/domain anchored terms first

Option B (`broad`) includes Option A plus medium-confidence terms:

- less frequent candidates
- broader lexical terms that may increase capture

## Impact preview

Before write, compute and show:

- estimated recategorized events
- estimated hours moved to target project
- remaining uncategorized delta
- top 3 sample matches per proposed rule

## Apply workflow

1. Generate A/B suggestions.
2. Show impact table and candidate list.
3. User chooses:
  - `A`
  - `B`
  - custom selection (optional v1.1)
  - cancel
4. On confirm:
  - create timestamped backup of config
  - apply rules atomically
  - show summary of written rules

## Safety and rollback

- Never mutate config without explicit confirmation.
- Always create backup before write.
- Keep writes atomic via existing `save_projects_config_payload`.

## Acceptance criteria

- New command(s) available and discoverable in `--help`.
- A/B suggestions shown for a real uncategorized dataset.
- Dry preview includes `+events/+hours/-uncategorized`.
- Confirmed apply writes only selected rules.
- Backup file is created and path printed.
- Unit tests cover:
  - suggestion split A vs B
  - preview math
  - apply path with backup
