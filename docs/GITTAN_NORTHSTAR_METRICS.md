# Gittan North Star Metrics

## Purpose

Turn Gittan vision into measurable product behavior.

This document operationalizes:

- `docs/GITTAN_VISION.md`
- `docs/ACCURACY_PLAN.md`
- Blueberry strategic context in `blueberry/private/northstar.md` and `blueberry/private/metrics.md`

## North Star Outcome

**Trusted reporting with low admin overhead.**

In practical terms:

- people trust the report,
- reports are quick to produce,
- and reporting quality improves over time.

## Metric Stack (what we track)

Use one stack with three levels:

1. **Product Quality** (is Gittan accurate and reliable?)
2. **Workflow Efficiency** (does Gittan reduce admin time?)
3. **Business Signal** (does Gittan improve pipeline and trust conversations?)

## 1) Product Quality Metrics

### 1.1 Attribution Accuracy

- **Definition:** Percentage of events/sessions correctly attributed to the intended project.
- **Formula:** `correct_attributions / total_attributions`
- **Source:** `docs/evals/latest.md` generated from golden dataset runs.
- **Target:** `>= 85%` (from `ACCURACY_PLAN.md`)
- **Cadence:** Weekly

### 1.2 Uncategorized Rate

- **Definition:** Share of events that remain unclassified.
- **Formula:** `uncategorized_events / total_events`
- **Source:** eval output + report payload summaries
- **Target:** `<= 15%`
- **Cadence:** Weekly

### 1.3 Session Hour Delta vs Baseline

- **Definition:** Difference between Gittan estimated hours and manual baseline.
- **Formula:** `abs(gittan_hours - manual_hours) / manual_hours`
- **Source:** pilot comparison sheet
- **Target:** `<= 20%`
- **Cadence:** Weekly during pilot cycles

### 1.4 Output Reliability

- **Definition:** Share of runs that successfully emit required outputs (summary + JSON, optionally HTML/PDF).
- **Formula:** `successful_runs / total_runs`
- **Source:** pilot run logs/checklist
- **Target:** `>= 95%` for core outputs
- **Cadence:** Weekly

## 2) Workflow Efficiency Metrics

### 2.1 Time to Review-Ready Report

- **Definition:** Time from run start to a report ready to review/share.
- **Formula:** `report_ready_timestamp - run_start_timestamp`
- **Source:** pilot self-report + command timestamps
- **Target:** `< 10 minutes` typical; stretch `< 5 minutes`
- **Cadence:** Per pilot run, summarized weekly

### 2.2 Correction Time

- **Definition:** Daily time spent correcting/massaging report results.
- **Formula:** tracked minutes/day
- **Source:** pilot feedback template
- **Target:** `< 3 min/day`
- **Cadence:** Weekly

### 2.3 Export Readiness

- **Definition:** Time to generate chosen export format(s) once range is selected.
- **Formula:** minutes from command start to output generated
- **Source:** run logs
- **Target:** `< 60 sec` for standard export path
- **Cadence:** Weekly

## 3) Business Signal Metrics

### 3.1 Pilot Activation Rate

- **Definition:** Share of pilots who complete at least one full reporting cycle.
- **Formula:** `activated_pilots / total_pilots`
- **Source:** pilot tracker
- **Target:** `>= 70%`
- **Cadence:** Bi-weekly

### 3.2 Pilot-to-Active Conversion

- **Definition:** Share of pilots who continue usage after trial period.
- **Formula:** `active_after_pilot / completed_pilots`
- **Source:** pilot tracker + follow-up logs
- **Target:** initial `>= 40%`, adjust when sample size grows
- **Cadence:** Monthly

### 3.3 Reporting Confidence Score

- **Definition:** User-rated confidence in sharing report with customer/manager.
- **Formula:** average of 1-5 score from feedback form
- **Source:** 5-question template
- **Target:** `>= 4.0 / 5`
- **Cadence:** Per pilot cycle

### 3.4 Inbound Signal Lift (Blueberry-facing)

- **Definition:** Change in qualified inbound conversations linked to Gittan content/case posts.
- **Formula:** period-over-period difference in qualified DMs/inquiries
- **Source:** manual CRM/content log
- **Target:** positive trend over rolling 8 weeks
- **Cadence:** Bi-weekly

## Guardrails (must not regress)

These are non-negotiable:

- **Local-first trust:** no forced cloud path in core workflow
- **Consent clarity:** source toggles and first-run consent remain explicit
- **Scope control:** avoid "track everything" expansion without KPI evidence

If a feature improves one metric but breaks these guardrails, do not ship.

## Weekly Review Ritual (45 minutes)

1. Run accuracy eval (`docs/ACCURACY_PLAN.md` workflow).
2. Review top mismatches and uncategorized clusters.
3. Pick one high-impact rule/refactor change.
4. Re-run and compare KPI deltas.
5. Log decisions in a short weekly note (what changed, what improved, what worsened).

## Monthly Product Review (60 minutes)

1. Summarize pilot activation/conversion/confidence.
2. Compare efficiency metrics (time-to-report, correction time).
3. Decide one roadmap priority for next month:
  - accuracy
  - onboarding UX
  - output reliability
  - integration/export value
4. Explicitly reject at least one out-of-scope idea to preserve focus.

## Suggested Dashboard Rows (simple starter)

- Week
- Attribution accuracy
- Uncategorized rate
- Hour delta
- Avg time-to-report
- Avg correction time
- Pilot activation
- Pilot-to-active
- Confidence score
- Notes / decisions

Keep this simple and manually maintain until automation clearly saves time.