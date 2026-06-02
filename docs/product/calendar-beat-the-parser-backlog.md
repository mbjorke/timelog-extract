# Backlog: beat the calendar parser (Pierre)

Status: product-owner backlog  
Last updated: 2026-06-01  
Role: product owner (planning only — no code in this doc)

Produced by the `gittan-product-owner` skill against the calendar scope. The
benchmark is [`persona-pierre-calendar-timereport.md`](persona-pierre-calendar-timereport.md);
the shared time target is
[`../specs/scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md).

## Definition of Done

Pierre says *"Gittan is better than my Calendar Event Parser & Time Tracker."*
That is reached when Tier 1–2 ship (he switches) and Tier 3 gives him something
his tool can't (he stays). Items below are ordered to reach a switchable product
fast, then leapfrog.

## Ordering

`now` → bridge spec (#135, in review) is the root. Then P1 (collector +
multi-calendar) and P2 (week pivot) are the switch-makers. P3–P4 are parity.
P5–P8 are the leapfrog wins that secure the DoD.

---

### P1 — Multi-calendar collector with role per calendar
- status: **built** — `collectors/calendar.py`, opt-in `--calendar-source on` + `--calendar-names "Name:role,…"`, fixtures in `tests/test_collectors_calendar.py`. How its hours are counted is still deferred to the bridge phase (P3+).
- priority: now (after bridge spec merges)
- problem: the prototype hardcodes one calendar ("Work"); Pierre's time lives in a
  dedicated `TimeReport` calendar plus others across Google/iCloud/org accounts.
- user value: Gittan reads the calendars he actually uses, with the right meaning.
- non-goals: per-provider API auth (read the local `Calendar.sqlitedb`); all-day
  events (excluded, D2); recurring expansion (v1 limit, D3).
- behavior:

```gherkin
Scenario: User selects calendars and assigns a role to each
  Given calendars "TimeReport" (time-report) and "Work" (meetings) are configured
  When Gittan collects calendar events
  Then TimeReport events map in as primary_claim (confirmed)
  And Work events map in as scheduled_context (proposed)
  And unconfigured calendars are not read
```

- acceptance: `collectors/calendar.py` reuses the SQLite path; config is a list of
  `{calendar, account, role}`; registered in `collector_registry.py` + `sources.py`;
  `collector_status` + doctor row (DB readable, Full Disk Access, which calendars).
- validation: fixture-SQLite tests (no live data) for role mapping, windowing,
  all-day exclusion, missing-DB → missing-prereq.
- dependencies: bridge spec (#135).

### P2 — Week × project pivot report view
- priority: now
- problem: Pierre trusts a `WeekNumber × project → TOTAL` pivot + weekly stacked
  chart; an unfamiliar report won't feel "better".
- user value: day-one familiarity; his existing mental model, no export step.
- behavior:

```gherkin
Scenario: Report shows hours by week and project
  Given classified events across several ISO weeks
  When the user runs the weekly pivot view
  Then rows are ISO week numbers, columns are projects, with per-row TOTAL
```

- acceptance: a report/output view building on `analytics.group_by_day` /
  `estimate_hours_by_day`, grouped by ISO week (`isocalendar`); terminal table now,
  JSON for later surfaces.
- validation: golden-fixture test of the pivot; CLI smoke.
- dependencies: P1 (for calendar-sourced rows), but usable on existing sources too.

### P3 — Classify his title codes to projects
- status: **built** — the engine already does this: the collector runs each event
  title through `classify_project`, and `normalize_profile` lowercases
  `match_terms` so capitalized codes match case-insensitively. Locked with
  regression tests (`tests/test_calendar_code_classification.py`) and a how-to
  ([`../sources/calendar-title-code-mapping.md`](../sources/calendar-title-code-mapping.md)).
- priority: next
- problem: titles encode projects as prefixes/codes (`HÅ-DAA`, `EASE-DAA`,
  `KidneySign`, …); must map even when sloppy.
- acceptance: titles run through `classify_project`; a documented way to map his
  codes via `match_terms`; unknown titles fall back without crashing.
- validation: unit tests over a sample of his code prefixes.
- dependencies: P1.

### P4 — Zero-export parity (live read)
- status: **built** — satisfied by P1 (Gittan reads the calendar live; no export
  step) + P2 (`--weekly` pivot). End-to-end onboarding runbook:
  [`../runbooks/calendar-time-report-onboarding.md`](../runbooks/calendar-time-report-onboarding.md).
- priority: next
- problem: his loop needs an export + manual upload; Gittan must remove it.
- acceptance: a single command produces the pivot live from the calendar(s) with
  no intermediate file.
- validation: demo/runbook showing no export step.
- dependencies: P1, P2.

### P5 — Corroboration (trust layer) — leapfrog
- priority: later
- problem: his timesheet is self-reported; Gittan can verify it.
- user value: "KidneySign 3h ✓ corroborated by 2.4h Cursor + 1 commit".
- behavior:

```gherkin
Scenario: Primary-claim hours are annotated, never overridden
  Given a time-report entry of 3.0h and 2.4h of work evidence in the window
  When the report is produced
  Then reported hours stay 3.0
  And a corroboration annotation may be shown
```

- acceptance: corroboration is annotation only (per evidence policy); confidence
  shown, entered hours authoritative.
- validation: test that hours are unchanged; annotation present.
- dependencies: P1, bridge.

### P6 — Gap nudges — leapfrog
- priority: later
- problem: he forgets to log; strong work evidence with no time entry is invisible.
- user value: "Tue 14–16: heavy financing-portal activity, no entry — log 2h?"
- acceptance: this is the bridge reconcile loop surfacing missing entries; writes
  `reported_time` only on confirm.
- dependencies: P1, P5, bridge reconcile phase.

### P7 — Onboarding: propose projects from calendar history — leapfrog
- status: **built** — `gittan calendar-suggest` (`core/cli_calendar_suggest.py`)
  reads titles via `collectors.calendar.read_calendar_titles` and ranks
  distinctive codes with `core/calendar_suggest.py`, skipping codes already in
  config; suggestion-only (never writes config). How-to in
  [`../sources/calendar-title-code-mapping.md`](../sources/calendar-title-code-mapping.md).
  Limitation: bare single-word project names aren't detected (by design).
- priority: later
- problem: setting up projects is friction; his history already encodes them.
- acceptance: scan TimeReport history, extract distinct title prefixes, propose
  project profiles (reuse triage/onboarding suggestion flow).
- dependencies: P1, P3.

### P8 — Last mile: invoice/client deliverable — leapfrog
- priority: later
- problem: his tool stops at charts.
- acceptance: confirmed `reported_time` → invoice draft / client hour report via
  existing output layer.
- dependencies: P1–P5, bridge.

---

## Risks / anti-goals (from persona)
- Never override his entered hours without consent (loses trust → he leaves).
- Don't require per-provider API setup if the local DB has the data.
- The first-run report must resemble his week × project pivot.
- Don't treat every calendar as the same role.

## Open decisions before P1 codes
- Confirm subscribed Google/iCloud calendars are present in the local
  `Calendar.sqlitedb` (removes the need for any API).
- Config location for `{calendar, account, role}` (ties to bridge open question on
  the `reported_time` store).
