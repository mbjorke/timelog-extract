# GH-414 Chrome Dashboard Evaporation — Measurement Pass

Date: 2026-07-25
Mode: golden eval over synthetic Chrome History fixtures (no real local data)
Purpose: `#414` asks for a measurement pass characterizing each mechanism
separately **before** a fix is designed. This is that pass. No collector or
thinning behavior was changed.

## Setup

180 synthetic Chrome visits to a single dashboard host, evenly spaced over 8h
on 2026-07-13, varying only the query string — the shape `#414` reports. The
fixture uses a neutral host (`dashboard.example`); the real case in `#414` was a
registrar/DNS control panel.

Two datasets differ in **one** thing: where the host is declared in the projects
config.

```bash
python3 scripts/run_golden_eval.py --check
python3 scripts/run_golden_eval.py --print-expectations \
  --dataset tests/fixtures/golden_chrome_dashboard_dataset.json
```

| Dataset | Host declared in |
|---|---|
| `golden_chrome_dashboard_dataset.json` | `match_terms` |
| `golden_chrome_dashboard_tracked_only_dataset.json` | `tracked_urls` only |

## Result

| Config shape | Events in report | Hours | Span |
|---|---|---|---|
| Host in `match_terms` | **36** of 180 visits | **7.78h** | preserved |
| Host in `tracked_urls` only | **0** | **0** | whole day gone |

Stage-by-stage on the same 180 rows, measured directly against the thinners:

| Stage | Rows kept | Span |
|---|---|---|
| Raw visits | 180 | 8.0h |
| `normalize_chrome_url` | 1 distinct URL | — |
| `thin_chrome_visit_rows` (12 min — the production value) | 36 | 7.8h |
| `thin_chrome_visit_rows` (30 / 60 min) | 15 / 8 | 7.5h / 7.2h |
| `thin_chrome_visit_rows_by_day` / `dedupe_web_visit_rows` | 1 | 0.0h |

## Verdicts on the hypotheses

**H1 — first-visit-per-day thinning ate the work.** `#414` names
`dedupe_web_visit_rows` / `thin_chrome_visit_rows_by_day` as mechanism 1.
**Falsified for this shape.** Those functions do collapse 180 rows to 1 (span
0.0h), but they are only reachable from the two collectors that hard-filter for
`claude.ai` and `gemini.google.com` (`collectors/chrome.py:255,302`). A
keyword-matched host goes through `collect_chrome` → the 12-minute window thinner,
which keeps 36 rows and **preserves the span**. Concentrated work is thinned, not
erased.

**H2 — a downstream drop removed surviving events.** `#414`'s mechanism 2.
**Not reproduced.** With the host in `match_terms`, all 36 surviving events reach
the report and bill 7.78h. Nothing downstream dropped them.

**H3 — the host was never queried (new).** **Confirmed.** `collect_chrome`
builds its SQL from `match_terms + profile name`
(`collectors/chrome.py:342-345`) — never from `tracked_urls`. A generic
`tracked_urls` host therefore has **no collector at all**: not `collect_chrome`
(not a keyword), not the claude.ai/gemini collectors (substring filters). The
visits are never read, which is exactly the reported symptom — "absent from the
report payload" — and it is invisible unless the host also happens to be a
`match_term`.

## What this means for the fix

The evaporation in `#414` is most consistent with a **config-shape coverage
hole**, not with thinning being too aggressive. That matters because the issue's
stated next step — "characterize each mechanism separately before changing
thinning behavior" — would have led to tuning a thinner that is not the cause.
Retuning the window would trade accuracy for nothing here.

Open for the maintainer, and why this pass stops short of a fix:

1. **Confirm the real config shape.** Was the 2026-07-13 registrar host in
   `tracked_urls` only? That decides whether H3 is the whole explanation or one
   of two.
2. **Product decision (`tracked_urls` semantics).** Should `tracked_urls` feed
   the Chrome keyword query, get its own generic collector, or stay
   claude.ai/gemini-specific with `doctor` warning about hosts no collector will
   ever read? These differ in scope and in what starts counting as billable —
   not an implementer's call.

## Tripwire

`golden_chrome_dashboard_tracked_only_dataset.json` records **current** behavior
(zero hours) with a `max_period_total_hours: 0` invariant. If `#414` is fixed and
that host starts producing hours, the dataset **fails on purpose** so the golden
record is updated as a conscious decision instead of drifting silently.

## Reproducibility

Fixtures are generated, not captured: `tests/golden_home_fixtures.py` seeds a
Chrome History SQLite into a throwaway `HOME` from a `synth` spec (evenly spaced,
no seed needed). All four golden datasets run in 1.8s and are exercised by
`tests/test_golden_eval.py` in the normal suite. No real browser history, no
client data.
