# Onboarding: calendar-based time reporting (zero-export)

Status: runbook  
Last updated: 2026-06-02

For someone who already tracks time in a calendar — a dedicated calendar (e.g.
`TimeReport`) whose events *are* the time entries, with the project encoded in
the title (`HÅ-DAA standup`, `KidneySign proteomics data`, `AXOR – OneFlow`).
See [`../product/persona-pierre-calendar-timereport.md`](../product/persona-pierre-calendar-timereport.md).

The goal of this runbook is the **zero-export** flow: Gittan reads the calendar
**live** and produces a week × project report, with **no export/upload step**.

## Before vs after

| | The old loop | With Gittan |
| --- | --- | --- |
| Get events | Export calendar → `calendar_events.txt` | Read live from the local Calendar DB |
| Aggregate | Upload the file to a parser app | `gittan report --weekly` |
| Set up projects | Hand-maintain the mapping | `gittan calendar-suggest` proposes them |

No file export, no upload — the calendar is read directly (read-only).

## One-time setup

1. **Grant Full Disk Access** to the terminal/app running Gittan (System
   Settings → Privacy & Security → Full Disk Access). The calendar lives in a
   protected SQLite store. Verify:

   ```bash
   gittan doctor
   ```

   The **Calendar** row should read "DB accessible". If it says "Full Disk
   Access required", grant it and re-run.

2. **Let Gittan propose your projects** from your calendar history:

   ```bash
   gittan calendar-suggest --calendar-names "TimeReport"
   ```

   It scans the named calendar, finds distinctive codes (hyphenated, CamelCase,
   ALL-CAPS, dotted), skips codes already in your config, ranks by frequency, and
   prints ready-to-paste profile stubs. It **never writes config** — review the
   names and paste the ones you want into your projects config. (Bare single-word
   project names aren't auto-detected; add those by hand.) Details:
   [`../sources/calendar-title-code-mapping.md`](../sources/calendar-title-code-mapping.md).

## Daily / reporting use

Run a report with the calendar source on, choosing which calendars to read and
their role (a dedicated time-report calendar is a `primary_claim`; a meetings
calendar is `scheduled_context`):

```bash
gittan report --last-month \
  --calendar-source on \
  --calendar-names "TimeReport:primary_claim,Work:scheduled_context" \
  --weekly
```

- `--weekly` adds the ISO week × project pivot (the familiar timesheet view).
- All-day events are excluded; recurring events are read as their stored
  instances (not expanded) in this version.

## Notes and limits

- **Read-only.** Gittan never writes to your calendar.
- **Observed/classified, not approved invoice time.** The weekly pivot is what
  Gittan observed and classified — review before billing.
- How calendar time is *counted* (meetings as supporting context vs a primary
  time claim, plus corroboration against real work evidence) is governed by the
  scheduled→reported bridge:
  [`../specs/scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md).
  Those reconciliation features are planned (backlog P5–P6 in
  [`../product/calendar-beat-the-parser-backlog.md`](../product/calendar-beat-the-parser-backlog.md)).
