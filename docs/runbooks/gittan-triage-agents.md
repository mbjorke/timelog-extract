# Gittan triage: agent and automation contract

Purpose: let **non-interactive agents** (Cursor, Claude, CI) reason about unexplained Screen Time days **without** `questionary` prompts or mutating `timelog_projects.json` by surprise.

## Safe commands

| Goal | Command |
|------|---------|
| **Read-only plan** (structured, stdout) | `gittan triage --json` (plus date range and limits as needed) |
| **Apply heuristics** (same rules as interactive `--yes`) | `gittan triage --yes` |
| **Human-driven** | `gittan triage` (no flags) |
| **Apply structured decisions** (e.g. mobile inbox) | `gittan triage-apply --input decisions.json` (writes config; use `--dry-run` first) |

`--json` **never** writes the config. It only prints one JSON object to **stdout** (stderr may contain warnings from collectors; for automation prefer a quiet machine if we add `--quiet-json` later).

**`triage-apply`** is the supported path for **batch / mobile** categorization: it validates a small **`decisions`** JSON and applies `tracked_urls` / `match_terms` rules. It creates a timestamped backup before writing when not `--dry-run` (see `core/cli_triage_apply.py`).

## JSON contract (`schema_version` 1) — `gittan triage --json`

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
  - Optional timestamp anchors (local time): `first_seen_local`, `last_seen_local`, `sample_window_local.start`, `sample_window_local.end`.
  - These are guidance hints for onboarding confidence, not hard evidence by themselves.
- `suggestions` — ranked project suggestions. Each entry includes `canonical`, score/hit fields, `ticket_mode`, `default_client`, and **`tags`** (from profile `tags` / `canonical_project`, for inbox/mobile labeling).
- **`question`** — short human-readable prompt for UIs (`null` if there are no suggestions).
- **`choices`** — compact options for pickers: objects with `canonical` (or `null` for “skip”), `tags`, and `label` (includes a final **“None of these / skip”** row).
- `resolved_project_for_top_suggestion` — string from `resolve_target_project_name`.
- `resolved_in_config` — whether that string is a known `project_names` entry.
- `yes_automation` — what `--yes` would do: `would_apply`, optional `target_project`, `domains`, or `reason` if it would skip.
- `skip_reason` — why a human/agent might skip this day (`no_chrome_sites`, `no_suggestions`, etc.) or `null`.

## Decisions JSON — `gittan triage-apply`

**Not** the same as `triage --json` output. Build this from your mobile client or tooling after the user confirms mappings.

Top-level shape:

```json
{
  "decisions": [
    {
      "project_name": "Exact profile name from timelog_projects.json",
      "rule_type": "tracked_urls",
      "rule_value": "example.com"
    }
  ]
}
```

- **`rule_type`**: `tracked_urls` or `match_terms` only.
- stdin: pass `-i -` and pipe JSON.
- **`--dry-run`**: prints JSON describing what would apply; no write.
- **`--allow-create`**: optional; if omitted, unknown `project_name` rows are errors.
- On success, stdout is JSON with `applied` / `skipped` / `errors`. Config writes call `backup_projects_config_if_exists` before mutation.

## Review workflow (including Cursor `/gittan-triage-review`)

1. Run `gittan triage --json --from … --to … --projects-config <path>` in a **copy** of config if needed.
2. Paste the JSON (or file path) into the review session.
3. Check: `resolved_in_config`, `yes_automation.would_apply`, `question` / `choices` if building a mobile UI, and `notes_for_agents`.
4. Only then run `gittan triage --yes …`, **`gittan triage-apply`** with a proper **decisions** payload, or edit `tracked_urls` manually — **do not** treat the triage plan JSON as input to `triage-apply`.

## Privacy

- Do not commit real `timelog_projects.json` or raw JSON that includes customer-specific domains.
- Prefer fixtures under `tests/` with generic domains.
