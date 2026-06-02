# Persona: Pierre — the calendar time-reporter

Status: product persona + competitive DoD  
Last updated: 2026-06-01

## Why this persona exists

Pierre already solved his own time tracking with Google Calendar plus a custom
Streamlit "Calendar Event Parser & Time Tracker". He is a realistic, demanding
first external user for Gittan's calendar work: he has a working tool, so Gittan
has to be **clearly better**, not merely present.

This doc is the **benchmark** the calendar/bridge work is measured against. The
collector contract and the
[`scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md)
implement *how*; this doc defines *what would make Pierre switch*.

## How Pierre works today

- He keeps a **dedicated calendar named `TimeReport`** (one of many calendars
  across Google, iCloud, and several org accounts). Each event in it is a
  **deliberate time entry**, not a meeting he attended.
- Event titles encode the project as a prefix/code: `KidneySign`, `HÅ-DAA`,
  `HÅ-EASE`, `HÅ-EuCo`, `EASE-DAA`, `Strike`, `immuniverse.bio`, …
- His loop: select events → export to `calendar_events.txt` → upload to a
  Streamlit app → see a **week × project pivot** (`WeekNumber × project →
  TOTAL`), a stacked weekly bar chart, and a few views (detailed events, weekly
  summary, current week, custom week).

## The key reframe

A `TimeReport` calendar is **not** `scheduled_context` (meetings that explain
time). Every event is a user-authored claim about worked time. So a calendar
source must support **role per calendar**, not one global role:

| Calendar kind | Evidence role | Maps to `reported_time` as |
| --- | --- | --- |
| Dedicated time-report (e.g. `TimeReport`) | `primary_claim` | `confirmed` directly — the user already authored it |
| Meetings / `Work` | `scheduled_context` | `proposed` — needs confirmation, never silent |
| Personal / family / holidays | ignored | not collected |

Implication: the source can't hardcode `"Work"`. Pierre needs to **select which
calendars to read and assign a role to each**, across multiple accounts.

Likely technical win to verify: subscribed Google/iCloud calendars sync into the
local macOS `Calendar.sqlitedb`, so the existing local-SQLite path can probably
read **all** his accounts without per-provider API auth.

## What "better than his parser" means (DoD)

Pierre's verdict — *"Gittan is better than my Calendar Event Parser & Time
Tracker"* — breaks down into layered, checkable wins:

### Tier 1 — Remove his current friction (table stakes)
- [ ] **No export step.** Gittan reads the calendar(s) live; `calendar_events.txt`
      and the manual upload disappear.
- [ ] **Recognizable week × project pivot.** A report view that matches his
      mental model (WeekNumber rows, project columns, TOTAL), so the output feels
      familiar from day one.

### Tier 2 — Parity on what he trusts
- [ ] Multi-calendar / multi-account selection with role per calendar.
- [ ] His title codes (`HÅ-DAA`, `EASE-DAA`, `KidneySign`, …) classify to Gittan
      projects via `match_terms` / `tracked_urls`, even when titles are sloppy.
- [ ] Weekly stacked distribution comparable to his chart (or a clearly better
      equivalent).

### Tier 3 — Leapfrog (this is where Gittan wins, not ties)
- [ ] **Corroboration / trust.** Cross-check a `TimeReport` claim against real
      work evidence: *"KidneySign 3h logged ✓ corroborated by 2.4h Cursor + 1
      commit."* Turns a self-reported timesheet into a **verified** one.
      **His entered hours stay authoritative** — corroboration is a confidence
      annotation, never an override.
- [ ] **Gap nudges.** Find windows with strong work evidence but **no**
      TimeReport entry: *"Tue 14–16: heavy financing-portal activity, no time
      entry — log 2h?"* (this is the bridge's reconcile loop).
- [ ] **Onboarding magic.** Scan his existing TimeReport history, extract distinct
      title prefixes, and **propose project profiles automatically** (ties into
      existing triage/onboarding).
- [ ] **Last mile.** He stops at charts; Gittan produces an invoice draft /
      client hour report.
- [ ] **Write-back (later).** From a confirmed `reported_time`, Gittan can create
      the TimeReport event or post to Toggl/Jira. The calendar stays his source of
      truth; Gittan fills the gaps.

## Anti-goals (how we lose Pierre)

- "Correcting" his entered hours against observed evidence without consent — he
  loses trust and goes back to his own tool.
- Requiring per-provider API setup when the local calendar DB already has the data.
- A report that looks nothing like his week × project pivot on first run.
- Treating every calendar as the same role (turning his family calendar into
  billable time).

## Relationship to other docs

- Evidence roles and the "no silent override" rule:
  [`../specs/source-evidence-policy.md`](../specs/source-evidence-policy.md).
- Shared `reported_time` target and reconcile contract:
  [`../specs/scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md).
- Collector responsibilities (status, doctor, fixtures, privacy):
  [`../specs/source-collector-contract.md`](../specs/source-collector-contract.md).
