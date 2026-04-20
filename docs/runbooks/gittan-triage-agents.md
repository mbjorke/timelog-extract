# Gittan triage: agent and automation contract

Purpose: let **non-interactive agents** (Cursor, Claude, CI) reason about unexplained Screen Time days **without** `questionary` prompts or mutating `timelog_projects.json` by surprise.

## Safe commands

| Goal | Command |
|------|---------|
| **Read-only plan** (structured, stdout) | `gittan triage --json` (plus date range and limits as needed) |
| **Apply heuristics** (same rules as interactive `--yes`) | `gittan triage --yes` |
| **Human-driven** | `gittan triage` (no flags) |

`--json` **never** writes the config. It only prints one JSON object to **stdout** (stderr may contain warnings from collectors; for automation prefer a quiet machine if we add `--quiet-json` later).

## JSON contract (`schema_version` 1)

Top-level keys:

- `schema_version` — integer, currently `1`.
- `command` — always `"gittan triage"`.
- `options` — echo of CLI options: `date_from`, `date_to`, `projects_config`, `max_days`, `max_sites`, `scoring_mode`.
- `project_names` — sorted list of profile `name` values from the chosen config (for validation).
- `empty_reason` — if no days with unexplained hours: `no_unexplained_days` or `null` when there are days.
- `days` — array of per-day objects (see below).
- `notes_for_agents` — short reminders (privacy, site-first, next steps).

Per-day object:

- `day` — `YYYY-MM-DD`.
- `gap` — `estimated_hours`, `screen_time_hours`, `unexplained_screen_time_hours` (numbers).
- `top_sites` — domains with visits and share; **page titles are omitted** in JSON to reduce accidental PII in logs.
- `suggestions` — ranked `ProjectSuggestion` fields (canonical, score, hit counts, `ticket_mode`, `default_client`).
- `resolved_project_for_top_suggestion` — string from `resolve_target_project_name`.
- `resolved_in_config` — whether that string is a known `project_names` entry.
- `yes_automation` — what `--yes` would do: `would_apply`, optional `target_project`, `domains`, or `reason` if it would skip.
- `skip_reason` — why a human/agent might skip this day (`no_chrome_sites`, `no_suggestions`, etc.) or `null`.

## Review workflow (including `/ultrareview`)

1. Run `gittan triage --json --from … --to … --projects-config <path>` in a **copy** of config if needed.
2. Paste the JSON (or file path) into the review session.
3. Check: `resolved_in_config`, `yes_automation.would_apply`, and `notes_for_agents`.
4. Only then run `gittan triage --yes …` or edit `tracked_urls` manually.

## Privacy

- Do not commit real `timelog_projects.json` or raw JSON that includes customer-specific domains.
- Prefer fixtures under `tests/` with generic domains.
