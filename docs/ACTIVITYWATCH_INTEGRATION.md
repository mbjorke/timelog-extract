# ActivityWatch — integration note (backlog)

## What it is

[ActivityWatch](https://activitywatch.net/) is an **open-source, local** time tracker: it records activity in **buckets** (e.g. window titles, URLs, AFK) and exposes a **timeline** in its web UI. It is **not** an AI product; it is **usage telemetry** that users run on their own machine.

## Why consider it for Gittan

- **Complementary signal:** A unified stream of “what was active when” without adding a **new bespoke collector per desktop app** (fewer vendor-specific parsers to maintain for generic “screen time” style evidence).
- **Optional source:** Many users will **not** run ActivityWatch; any integration should remain **opt-in** and degrade gracefully when the daemon or data is absent.
- **Community scale:** A large user base and public backlog indicate **sustained interest** in local tracking, but also competing feature requests — Gittan should not depend on AW solving categorization or billing policy.

## What it does *not* replace

- **Project / customer mapping** and **billable vs non-billable** rules remain **Gittan’s** concern (profiles, `match_terms`, worklog, calendar, etc.).
- ActivityWatch is a candidate **input channel**, not a substitute for **project configuration** or **invoicing semantics**.

## Possible integration shape (not implemented)

1. Read events for the report date range from an **export**, **local API**, or **bucket store** (format and stability TBD when/if work starts).
2. Normalize to the same internal **event** model as other collectors (`source`, `local_ts`, `detail`, then `classify_project`).
3. Register as an **optional** collector with clear **disable reasons** when AW is not installed or not running.

## Status

**Backlog / exploratory.** No code path in Gittan consumes ActivityWatch data today. Revisit after higher-priority sources (e.g. calendar / CalDAV) if solo-founder workflows still benefit from aggregated window/URL timelines.
