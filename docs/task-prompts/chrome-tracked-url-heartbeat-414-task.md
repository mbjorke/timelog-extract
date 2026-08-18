# Chrome tracked-URL per-window heartbeat (GH-414)

Spec: `docs/specs/source-evidence-policy.md` (Claude.ai / Gemini web are
`passive_context`). Prior art: `docs/task-prompts/passive-web-duration-noise-task.md`
(GH-164 calendar-day collapse). Measurement: `docs/evals/gh-414-chrome-dashboard-measurement.md`.

## Problem

Tracked-URL collectors (`collect_claude_ai_urls` / `collect_gemini_web_urls`)
collapsed every normalized URL to **one first visit per UTC calendar day**
(`WEB_VISIT_COLLAPSE_MINUTES = 24*60` + `thin_chrome_visit_rows_by_day`). Sustained
same-chat / same-app work lost its wall-clock span before session math could use
it — concentrated single-URL work was punished while tab-hopping was rewarded.

## Scope (this slice)

- Replace daily first-visit collapse with a **bounded per-window heartbeat**
  (reuse `chrome_collapse_minutes`, default 12 — below the 15-minute session gap).
- Reset the rolling window at **UTC midnight** so calendar-day boundaries stay
  separate.
- Fixture tests for sustained / same-window / sparse / midnight / session continuity.
- Document root cause of the original “downstream drop” case and ownership split
  vs GH-410.

## Non-goals (GH-410 / deferred)

- General `collect_chrome` rolling thinner and its SQL keyword pre-filter.
- Keyword-gated infra/DNS host collection (registrar panels with no match_term).
- Query-string retention in `normalize_chrome_url`.
- Downstream `Uncategorized` rescue via `filter_included_events` / block inheritance.
- Rewriting the presence/block model wholesale (#410).
- Separate `--web-collapse-minutes` CLI flag (GH-164 non-goal).

## Ownership split / downstream root-cause

| Mechanism | Finding | Owner |
| --- | --- | --- |
| Tracked-URL per-day collapse | Real for Claude.ai / Gemini; fixed here with heartbeat | **#414** (this slice) |
| Keyword-gated SQL exclusion | Dominant for infra hosts with no `match_terms` — visits never leave SQLite | **GH-410** |
| Uncategorized filter drop | Events that classify as `Uncategorized` are dropped unless rescued (`Lovable (desktop)` / label anchors) | **GH-410** (block/anchor inheritance) |
| Generic `tracked_urls` host | Not collected by Claude/Gemini filters nor by `collect_chrome` keywords — coverage hole | document + tripwire golden; product decision deferred |

#419 impact-sort noise is reduced when tracked-web evidence keeps span, but full
fix depends on GH-410 block inheritance.

## Acceptance

```gherkin
Feature: Tracked web visits keep sustained-block temporal spread

  Scenario: Sustained same-URL run emits periodic heartbeats
    Given many Claude.ai visits to the same normalized URL over several hours
    When Claude.ai (web) is collected with default collapse
    Then more than one event should be emitted
    And the event count should stay well below the raw visit count

  Scenario: Visits within one cadence window collapse to one
    Given three Claude.ai visits to the same URL inside a 12-minute window
    When Claude.ai (web) is collected with default collapse
    Then only one event should be emitted

  Scenario: UTC midnight still splits calendar days
    Given two Claude.ai visits ten minutes apart across UTC midnight
    When Claude.ai (web) is collected with default collapse
    Then one event should be emitted for each UTC calendar day

  Scenario: Periodic heartbeats form one session
    Given heartbeats spaced under the 15-minute session gap for about two hours
    When sessions are computed
    Then they should form a single gap-clustered session with multi-hour span
```

## Traceability

- story_id: GH-414
- spec_status: approved
- implementation_status: built
- created_at: 2026-08-18
- last_updated_at: 2026-08-18
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/560
- implementation.branch: task/chrome-evaporation-414
- implementation.commits: [0e91109]
- validation.evidence: tests/test_chrome_web_collapse.py; docs/evals/gh-414-chrome-dashboard-measurement.md; bash scripts/run_autotests.sh
- validation.decision: conditional GO
- changelog:
  - 2026-08-18: Initial slice — tracked-URL per-window heartbeat; GH-410 owns infra/uncategorized.
  - 2026-08-18: PR #560 opened; autotests green.
