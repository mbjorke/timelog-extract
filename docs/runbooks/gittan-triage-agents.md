# Gittan triage: agent and automation contract

Purpose: let **non-interactive agents** (Cursor, Claude, CI) map URL hosts to projects **without** surprise writes to `timelog_projects.json`.

## Canonical commands (2026-05)


| Goal | Command |
| --- | --- |
| **Interactive URL → project mapping** | `gittan review` (date flags as needed) |
| **Read-only URL candidates** (stdout JSON) | `gittan review --json` |
| **Rule hit audit** (zero-hit terms, `top_hosts`) | `gittan projects-audit --json` |

`gittan review --json` **never** writes config. Schema: `schema_version` `1`, `command` `"gittan review"`, `candidates[]` with `url_key`, `suggested_project`, confidence, impact (see `core/cli_triage_map_context.py`). `gittan triage-map` is a deprecated alias with the same behavior.

## Deprecated (removal planned)

`gittan triage`, `gittan triage-domains`, `gittan triage-guided`, `gittan triage-apply`, and `gittan triage-map` still run but print a stderr deprecation notice. Prefer **`gittan review`** for URL mapping; use **`projects-audit` / `projects-trim`** for stale-rule hygiene.

Legacy sections below document the old `gittan triage --json` day-plan contract until those commands are removed.

## Legacy safe commands (`gittan triage` — deprecated)


| Goal | Command |
| --- | --- |
| **Read-only day plan** (structured, stdout) | `gittan triage --json` |
| **Human-driven day loop** | `gittan triage` (deprecated) |
| **Apply structured decisions** (mobile inbox) | `gittan triage-apply --input decisions.json` (deprecated; use `gittan review` interactively when possible) |


`--json` **never** writes the config. It only prints one JSON object to **stdout** (stderr may contain warnings from collectors).

`triage-apply` validates a small `decisions` JSON and applies `tracked_urls` / `match_terms` rules. It creates a timestamped backup before writing when not `--dry-run` (see `core/cli_triage_apply.py`).

## Beta onboarding use

For early testers, treat triage as the first controlled path from "Gittan runs"
to "my project config is useful":

1. Run `gittan triage --json` to generate a read-only evidence plan.
2. Review `top_sites` with local timestamp hints to recognize the real work
  window.
3. Treat `suggestions`, `question`, and `choices` as classified candidates, not
  invoice truth.
4. Apply only confirmed mappings with `gittan triage-apply --dry-run` first,
  then without `--dry-run` after the user approves.

This aligns with the Timelog Truth Standard split: observed evidence first,
classified candidates second, explicit human approval before writes.

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
- `suggestions` — ranked project suggestions. Each entry includes `canonical`, score/hit fields, `ticket_mode`, `default_client`, and `tags` (from profile `tags` / `canonical_project`, for inbox/mobile labeling).
- `question` — short human-readable prompt for UIs (`null` if there are no suggestions).
- `choices` — compact options for pickers: objects with `canonical` (or `null` for "skip"), `tags`, and `label` (includes a final "None of these / skip" row).
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

- `rule_type`: `tracked_urls` or `match_terms` only.
- stdin: pass `-i -` and pipe JSON.
- `--dry-run`: prints JSON describing what would apply; no write.
- `--allow-create`: optional; if omitted, unknown `project_name` rows are errors.
- On success, stdout is JSON with `applied` / `skipped` / `errors`. Config writes call `backup_projects_config_if_exists` before mutation.

## Review workflow (including Cursor `/gittan-triage-review`)

1. Run `gittan triage --json --from … --to … --projects-config <path>` in a **copy** of config if needed.
2. Paste the JSON (or file path) into the review session.
3. Check: `resolved_in_config`, `yes_automation.would_apply`, `question` / `choices` if building a mobile UI, and `notes_for_agents`.
4. Only then run `gittan triage --yes …`, `gittan triage-apply` with a proper `decisions` payload, or edit `tracked_urls` manually — **do not** treat the triage plan JSON as input to `triage-apply`.

## Privacy

- Do not commit real `timelog_projects.json` or raw JSON that includes customer-specific domains.
- Prefer fixtures under `tests/` with generic domains.

