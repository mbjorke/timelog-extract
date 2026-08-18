# Vision-anchored backlog — 2026-08-18 (product owner)

Planning artifact. No feature code. Produced because the backlog had drifted
into one kind of work, measured below rather than asserted.

## Traceability

- story_id: `none — opened when work starts` (per the `gittan-product-owner`
  issue-lifecycle rule changed 2026-08-18; this pass deliberately opens nothing)
- spec_status: `draft`
- implementation_status: `not built (planning artifact — no code)`
- created_at: `2026-08-18`
- last_updated_at: `2026-08-18`
- implementation.pr: `n/a`
- implementation.branch: `n/a`
- implementation.commits: `[]`
- validation.evidence: measurements in *The gap*, taken from the live tracker
  and `docs/product/gittan-northstar-metrics.md`
- validation.decision: `GO for the planning claims only` — it asserts nothing
  about unbuilt work
- changelog:
  - `2026-08-18: Initial pass. Anchored in the vision's three-level metric stack.`
  - `2026-08-18: Added V-7 (synthetic operator personas) as the vehicle for level-2 measurement, extending the existing golden-home materializer (GH-531). Records the hard boundary that personas may not emit level-3 numbers.`

---

## The gap

`docs/product/gittan-northstar-metrics.md` defines the north star — **"trusted
reporting with low admin overhead"** — as a stack of three levels:

1. **Product Quality** — is Gittan accurate and reliable?
2. **Workflow Efficiency** — does Gittan reduce admin time?
3. **Business Signal** — does Gittan improve pipeline and trust conversations?

Measured against the 41 open issues on 2026-08-18:

| Level | Metrics defined | Open issues serving it | Instrumented |
| --- | --- | --- | --- |
| 1 Product Quality | 4 (attribution accuracy, uncategorized rate, session-hour delta, output reliability) | **31 of 41 (76%)** | yes — `accuracy-plan.md`, golden eval in CI |
| 2 Workflow Efficiency | 3 (time-to-review-ready, correction time, export readiness) | few, incidental | **no** |
| 3 Business Signal | 4 (pilot activation, pilot-to-active, reporting confidence, inbound lift) | **1** (GH-416, `next`) | **no** |

**The finding is not that the vision is missing from the docs. It is that the
vision defines a scoreboard the current work cannot move.**

Levels 2 and 3 already have definitions, formulas, targets and cadences written
down — `>= 70%` pilot activation, `>= 40%` pilot-to-active, `>= 4.0/5` reporting
confidence. None of them has ever produced a number, because nothing generates
the input. Level 1, the one level that *is* instrumented, is also the one
receiving three quarters of the work.

Two consequences worth stating plainly:

- Half of the north star — "low admin overhead" — is currently **unfalsifiable**.
  Nothing measures how long a report takes to produce or correct.
- Every level-1 item improves a number that is already measured and already
  reasonably good. The marginal honest value of the 31st attribution fix is
  lower than the first measurement of levels 2 or 3.

### Applying the vision's own decision filter

`gittan-vision.md` ships five questions to ask before adding a source, output or
workflow step. Question 2 is *"does this reduce or increase user admin burden?"*
and question 5 is *"is this in-scope for v1/v1.1, or just technically possible?"*.
Neither question can currently be answered with evidence, for any item. That is
the concrete cost of the missing instrumentation, and it is why this pass ranks
measurement above further correctness.

---

## Backlog

### V-1 — Make "low admin overhead" measurable

- priority: **now**
- problem: Half the north star has no number. Metric 2.1 (time to review-ready
  report) and 2.2 (correction time) are defined with targets and never computed.
- user value: The product can tell whether it is getting *easier*, not just more
  accurate. Today it can only prove the latter.
- non-goals: no telemetry leaving the machine; no new cloud surface. This is a
  local measurement of the operator's own runs, consistent with local-first.
- behavior: record, locally, how long a report takes from invocation to a
  review-ready output, and how much correction follows it (edits to mapping,
  re-runs, manual overrides). Surface as a trend, not a single number.

```gherkin
Feature: Admin-overhead measurement
  The product can show whether reporting is getting cheaper, not only truer.

  Scenario: A report run records its own cost
    Given the operator produces a report for a period
    When the run completes
    Then the elapsed time to a review-ready output is recorded locally
    And no measurement leaves the machine

  Scenario: Correction effort is attributed to the report it followed
    Given a report has been produced
    When the operator corrects a mapping or re-runs within the same period
    Then that correction is counted against that report's cost
    And the trend over several periods is reportable
```

- acceptance:
  - metrics 2.1 and 2.2 produce a real number for at least four past periods
    (backfillable from the shadow log and observed cache where possible);
  - the numbers appear in a form the weekly review ritual can read;
  - nothing is transmitted; the measurement is local and inspectable.
- validation: computed values for four periods, checked by hand against one
  known run; `run_autotests.sh` green.
- dependencies: none blocking. Uses evidence that already exists.

---

### V-7 — Synthetic operator personas as the measurement vehicle

- priority: **now** (this is *how* V-1 and V-4 get built)
- problem: levels 2 and 3 are unmeasured, and the obvious fix — wait for a human
  — makes measurement hostage to recruiting a pilot.
- insight: **most of level 2 is not a property of the human at all.** Time to a
  review-ready report, correction effort and export readiness measure *how much
  the system needs a person*, which is a property of the data and the config.
  That is measurable against fabricated data, deterministically, in CI.
- existing ground: `tests/golden_home_fixtures.py` already materializes
  synthetic source data into a throwaway HOME ("no real local data, no
  network"), and `scripts/run_golden_eval.py` runs four datasets in CI. It
  covers **2 of ~24 collectors** (GH-531). Personas extend that, they do not
  replace it.
- behavior: named operator personas, each a config profile plus a multi-source
  synthetic HOME, representing the audiences in `gittan-vision.md`:
  a solo consultant with few clients; an agency operator with many; a
  repo-heavy developer; and **a designer with no repositories and no IDE
  traces**. Run the full report path for each and emit the level-2 metrics.

```gherkin
Feature: Persona-measured admin overhead
  Reporting cost is measured against fabricated operators, in CI, with no human.

  Scenario: A persona yields level-2 numbers
    Given a persona with a synthetic HOME and config
    When the full report path runs for a period
    Then time to a review-ready output is recorded
    And the number of manual interventions the output would require is counted
    And export readiness for that period is decided without a human

  Scenario: A regression in admin overhead fails the build
    Given personas have an established baseline for correction effort
    When a change makes a persona's report need more manual intervention
    Then the gate reports the regression against that baseline

  Scenario: A persona reveals an audience the product serves badly
    Given the designer persona has no repository and no IDE traces
    When the report runs
    Then whatever Gittan can honestly say about that operator's day is recorded
    And a persona that produces an unusable report is a finding, not a failure
```

- acceptance:
  - at least four personas materialize and run end to end in CI;
  - metrics 2.1, 2.2 and 2.3 produce numbers per persona per period;
  - baselines are recorded so a later change can be compared against them;
  - **no persona emits a level-3 number** (see the boundary below).
- validation: `run_autotests.sh` green with personas wired in; one persona's
  numbers checked by hand against a manual run.
- dependencies: extends GH-531's materializer coverage; that issue and this item
  should be done together rather than twice.

#### The boundary — what personas must never fake

Level 3 measures human judgement and behaviour: pilot activation, pilot-to-active
conversion, **reporting confidence** (a 1-5 human rating of whether they would
send the report to a customer), and inbound lift. A fabricated persona cannot
hold an opinion about a report.

Emitting a synthetic number for any of these would make the scoreboard look
green while measuring nothing — strictly worse than an empty cell, because an
empty cell is honest. **Personas serve level 2 and are forbidden from level 3.**

This is the same discipline the source-evidence policy already applies: a source
can be good evidence for context without being evidence for billable truth.

#### What this changes about V-2

Personas do **not** replace the pilot; they make it worth more. Every friction a
persona can find is friction the human pilot should not be spent discovering. The
scarce human is then spent on the only questions they can answer: *is this report
one I would actually send to my customer, and would I keep using this?*

---

### V-2 — One real pilot, end to end

- priority: **now**
- problem: Level 3 has four metrics, four targets, and zero data, because there
  has been no external pilot. GH-416 is the only issue that would produce any of
  it and it sits at `next` behind twenty-one others.
- user value: the only way to learn whether the 31 open correctness items matter
  to anyone other than the maintainer.
- non-goals: not a launch, not marketing, not pricing. One person, one full
  reporting cycle.
- behavior: take GH-416 (beta onboarding dry-run) as written and run it to a
  completed reporting cycle, capturing metrics 3.1 and 3.3 as a by-product.

```gherkin
Feature: First external pilot
  A person who is not the maintainer completes a full reporting cycle.

  Scenario: A pilot completes one reporting cycle
    Given an external tester installs Gittan from the published package
    When they produce a customer-facing report for one period
    Then pilot activation is recorded for that pilot
    And a reporting-confidence score is collected
    And every point where they needed help is written down

  Scenario: Pilot friction outranks maintainer intuition
    Given the pilot reported friction at a specific step
    When the backlog is next ordered
    Then that friction is ranked against the current now band on evidence
    And it is not deferred merely because it was not already on the list
```

- acceptance: one external tester completes install → report → customer-facing
  output; metrics 3.1 and 3.3 have their first real values; friction points are
  written down verbatim, not summarized into existing issues.
- validation: the pilot's own output plus the friction log.
- dependencies: **decision needed** — who the pilot is. This is the whole item;
  everything else about it is already specified in GH-416.

---

### V-3 — Resolve the agent-surface contradiction (MCP)

- priority: **next**
- problem: three committed documents disagree, and none is marked superseded:
  `docs/specs/intent-capture-agent-surface.md` argues **for** MCP as the one
  interface Claude Code, Claude Desktop and Cursor share;
  `docs/ideas/conversational-ui-stack.md` has a section titled *"Why no MCP"*;
  `docs/product/external-integrations.md` describes the target state as
  *"no MCP, no protocol layer"*.
- user value: an unresolved contradiction in committed docs silently blocks a
  whole direction — nobody can plan an agent surface while the repo argues with
  itself.
- non-goals: **not** building an MCP server in this item. Deciding only.
- behavior: one decision doc that answers the vision's five filter questions for
  the agent surface, states the choice, and marks the losing documents
  superseded. Filter question 3 is the crux: cloud/agent access must stay
  *optional, explicit and minimal* — an MCP surface must be shown to satisfy that
  or be rejected on it.
- acceptance: a decision record exists; the two non-chosen documents carry an
  explicit superseded marker; no code changed.
- validation: n/a (decision artifact).
- dependencies: none. Deliberately ranked `next`, not `now`: it unblocks a
  direction but produces no measurable movement on levels 2 or 3 by itself.

---

### V-4 — Export readiness as a measured property

- priority: **next**
- problem: metric 2.3 (export readiness) is defined and unmeasured, while
  customer-facing output is a *core promise* in `gittan-vision.md`.
- behavior: define what "ready to send" means concretely, then measure the share
  of periods that reach it without manual intervention.
- acceptance: metric 2.3 produces a number for four past periods.
- dependencies: V-1 (shares the measurement plumbing).

---

### V-5 — Distribution and marketplace

- priority: **later**
- problem: the vision's business-signal metrics assume users arrive somehow, and
  no item covers how.
- why `later`: sequencing, not disinterest. Distribution before a single
  completed pilot optimizes reach for an experience nobody has validated. V-2
  must produce its friction log first.

---

### V-6 — Further source coverage

- priority: **do not build yet**
- why: sources improve level 1, the only instrumented and best-served level.
  Framer (`framer-source-task.md`) is already demoted on its own merits; this
  entry generalizes the rule. A new source should wait until a pilot asks for it
  by name, which is exactly the demand signal the Framer pass found missing.
- promotion trigger: a pilot names the missing source in the V-2 friction log.

---

## Summary

| Item | Priority | Level it moves |
| --- | --- | --- |
| V-7 Synthetic operator personas (vehicle for V-1/V-4) | **now** | 2 |
| V-1 Make admin overhead measurable | **now** | 2 |
| V-2 One real pilot, end to end | **now** | 3 |
| V-3 Resolve the MCP contradiction | next | enables |
| V-4 Export readiness measured | next | 2 |
| V-5 Distribution and marketplace | later | 3 |
| V-6 Further source coverage | do not build yet | 1 (over-served) |

**The thesis in one line: stop adding to the level that is already measured, and
start measuring the two that are not.**

## Open decisions

1. **Who is the V-2 pilot?** Still the only human-blocked item — but no longer
   blocking *measurement*, since V-7 carries level 2 without a person.
2. **Does an MCP surface satisfy filter question 3** (optional, explicit,
   minimal)? Owned by V-3, not assumed here.
3. **Does the existing level-1 `next` band get demoted?** This pass does not
   demote the 22 `next` items; it argues they are collectively over-weighted.
   Re-ranking them individually is the next pass, and should happen *after* V-2
   produces friction evidence, so it is ranked on data rather than taste.

## Non-goals

- No issues opened by this pass, per the changed issue-lifecycle rule.
- No telemetry leaving the machine for any measurement item.
- No demotion of in-flight work (GH-544, GH-550) — this is about what comes
  after, not about interrupting.
