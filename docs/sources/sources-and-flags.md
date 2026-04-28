# Sources and flags — how collection works

This document explains how **data sources**, **CLI flags**, and `**--exclude`** interact. It exists so expectations match the implementation (see `core/pipeline.py`, `core/collector_registry.py`, `core/analytics.py`).

## There is no shared “base timeline”

Each **collector** either **runs** for the requested date range and **returns a list of events**, or is **skipped** (disabled / missing prerequisites / error). Events are **concatenated** into one list (`collect_all_events` in `core/pipeline.py`).

- **Turning off a source** means that collector **does not read** its backing store and contributes **zero** events. Nothing is “still there but hidden.”
- **Turning on a source** means that collector **may** produce events, subject to what exists on disk and the date range.

So: sources are **not** filters on a single precomputed dataset; they are **independent producers** merged at report time.

## Source toggles (consent / availability)

Examples include `--chrome-source`, `--mail-source`, `--github-source` (see CLI help for exact names and defaults).

`core/collector_registry.build_collector_specs` marks collectors as enabled or disabled with an optional **reason** (e.g. consent off, database not found, no GitHub username). Disabled collectors are not invoked; enabled ones run and append events.

Toggl follows the same pattern with **auto-detection**: when `TOGGL_API_TOKEN` exists, the Toggl source is enabled; otherwise it is disabled with a clear reason in `collector_status`.

Jira worklog posting is available via `gittan jira-sync` (separate from source collection). It uses `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`, and supports dry-run plus per-worklog confirmation before posting.

## Per-collector status in JSON output

When you use `--format json`, the truth payload includes `**collector_status`**: for each named source, whether it was **enabled**, a **reason** string when disabled or failed, and **how many raw events** that collector returned (`core/truth_payload.py`).

Use this to answer “why is Chrome/GitHub/etc. empty?” without guessing.

The Rich terminal report does **not** print the full `collector_status` table; it shows a **Source Summary** built from **actual events** (counts by `source` field) after inclusion rules.

## `--exclude` is not “exclude this source”

`--exclude` takes **comma-separated keywords**. In `core/analytics.group_by_day`, any event whose `**detail`** text contains one of those keywords (case-insensitive) is **skipped when grouping by day** for session/hour estimation.

- Collection has **already happened**; `--exclude` only affects **which events participate** in that aggregation step.
- It does **not** match on source name; it matches **substrings in the event detail string**.

If you want to drop an entire source from the report, use **source toggles** (or post-process JSON), not `--exclude`.

## Empty or near-empty reports

If **no** events survive deduplication and inclusion filters, or every collector is off or fails, you get **no activity** for the period (e.g. `gittan status` may print that no activity was tracked).

**Practical checks:**

1. `gittan doctor` — paths and permissions for local files (Chrome, Mail, Cursor, etc.).
2. `--format json` — inspect `**collector_status`** and `**totals.event_count**`.
3. Ensure **opt-in sources** are actually enabled (e.g. GitHub username + `--github-source` when you want it on).
4. For **project classification**, remember that **uncategorized** events may be hidden unless `--include-uncategorized` (see `core/events.py`).

## Related docs

- `docs/runbooks/manual-test-matrix-0-2-x.md` — manual scenarios (including “no config file” vs minimal JSON).
- `docs/runbooks/versioning.md` — package version vs JSON payload `version` field.
- `docs/runbooks/jira-worklog-sync.md` — setup and usage for Jira worklog posting.