# Report hours must visibly reconcile (product-owner)

Product-owner planning pass triggered by a real `gittan report --today` run whose
numbers did not appear to add up. No code is changed here — this is the ordered,
behavior-ready backlog and the reasoning behind it.

**Observed (2026-07-10):**

```
Observed timeline hours  1.8h  (1.6 attended/mixed + 0.2 agent)
gittan.sh                1.4h (1.1 + 0.2)      ← 1.1 + 0.2 = 1.3, not 1.4
project-hour total       1.9h                  ← vs 1.8h timeline
```

**Decision filter (from `docs/product/gittan-vision.md`):** does the report show
the operator numbers they can *trust and defend*? Soul #2 is "Proof over
performance theater — output should be understandable and reviewable"; soul #4 is
"Trust is a feature." A report whose displayed parts do not add up to its
displayed total erodes trust **even when the underlying accounting is correct** —
and here the split is also printed on the invoice PDF, so it reaches the customer.

## Grounding: the accounting is sound; the presentation is not

- `core/project_hours.py:313-319` adds each session-chunk to `hours` **and** to
  exactly one of `attended_hours` / `agent_hours` / `mixed_hours`. So by
  construction `hours == attended + mixed + agent` — no hour leaks, no missing
  category.
- `outputs/terminal_report_sections.py:378` and `outputs/terminal.py:225` render
  the split as `({attended+mixed:.1f} + {agent:.1f})` next to a separately
  rounded total. Each of the three numbers is rounded to one decimal
  **independently**, so true `1.38 → 1.4` while its parts `1.14 / 0.24 → 1.1 /
  0.2` — the parts visibly sum to 1.3, not the 1.4 shown.
- The same split feeds the invoice note (`outputs/pdf.py:49`, GH-284 slice 2).

So finding #1 is a **presentation/rounding** defect, not a money defect. Finding
#2 (timeline 1.8 vs project-total 1.9) is a **cross-granularity** question that
needs its root cause verified before it is called a bug.

## Traceability

- story_id: `pending` (issue created on approval via `/docs-to-issues`)
- spec_status: `draft`
- implementation_status: `not built` (planning artifact — no code)
- created_at: `2026-07-10`
- last_updated_at: `2026-07-10`
- implementation.pr: pending
- implementation.branch: `claude/codebase-unknowns-el498z`
- implementation.commits: []
- validation.evidence: this backlog + the observed run above
- validation.decision: `GO` (as a planning deliverable)
- changelog:
  - `2026-07-10: Initial pass; split-rounding grounded as presentation defect, timeline/total gap flagged for root-cause.`

## Ordering at a glance

| # | Item | Trust impact | Effort | Priority |
| - | ---- | ------------ | ------ | -------- |
| 1 | Displayed split must reconcile with displayed total | High (numbers don't add up; reaches invoice) | Low | **now** |
| 2 | Timeline total vs project-hour total must reconcile or be explained | Medium (two headline totals disagree) | Medium (verify first) | **next** |
| 3 | One documented reconciliation invariant for the whole report | Prevents recurrence | Low-medium | **later** |

---

## now

### Displayed hour splits reconcile with their displayed total

- priority: now
- problem: the `(attended+mixed + agent)` split is rendered by rounding each
  component and the total independently, so a row can read `1.4h (1.1 + 0.2)`.
  The underlying values reconcile exactly (see grounding); only the rounding of
  the display breaks the "parts add up to the whole" contract. It appears in the
  terminal report and on the invoice PDF.
- user value: every hours cell passes the first sanity check a human applies —
  the pieces sum to the total — so the operator trusts the report at a glance.
- non-goals:
  - Do not change session, allocation, or billing math (it is correct).
  - Do not drop the attended/agent split — make it *reconcile*, not disappear.
- behavior:

```gherkin
Feature: Displayed hour parts always sum to the displayed total
  Wherever a total is shown with an attended/agent breakdown, the rounded parts
  add up to the rounded total — in the terminal and on the invoice PDF.

  Scenario: A row whose true parts round in different directions
    Given a project with 1.38h total, 1.14h attended/mixed and 0.24h agent
    When the project-hour review row is rendered
    Then the displayed parts sum exactly to the displayed total
    And no row shows parts that contradict its total (e.g. never "1.4h (1.1 + 0.2)")

  Scenario: The invoice PDF split matches the invoice total
    Given the same project appears on the invoice note
    Then the split shown on the PDF reconciles with the PDF total
```

- acceptance:
  - A shared rounding helper renders the total and its parts so the parts always
    sum to the total (largest-remainder / "render total as the sum of rounded
    parts", or added precision — chosen in the open decision below).
  - Applied at `outputs/terminal_report_sections.py:378`, `outputs/terminal.py:225`,
    and the invoice note in `outputs/pdf.py`.
- validation: unit test on the rounding helper with a case where naive
  independent rounding mismatches (e.g. 1.14 / 0.24 / total 1.38); a terminal
  snapshot of that row.
- dependencies: none blocking; touches outputs only, not core math.

---

## next

### Timeline total and project-hour total reconcile — or the report explains the gap

- priority: next (verify root cause first; fix or footnote follows)
- problem: the observed run shows `Observed timeline 1.8h` but a project-hour
  total of `1.9h`. Hypothesis: per-project minimum-session flooring
  (`session_duration_hours` floor applied per project via
  `allocate_session_hours_by_project`) inflates the summed project totals above
  the single timeline total; i.e. a cross-granularity artifact, not lost/extra
  work. This must be **verified**, not assumed.
- user value: the two headline numbers a user reads first either agree, or the
  report says in one line why they differ — so the difference never reads as a
  bug.
- non-goals:
  - Do not remove minimum-session flooring (it is a deliberate billing floor).
  - Do not reconcile by silently hiding the smaller number.
- behavior:

```gherkin
Feature: Headline totals reconcile or are explained
  The timeline total and the summed project-hour total do not silently disagree.

  Scenario: Per-project flooring inflates the project sum
    Given several small per-project sessions each lifted to the session floor
    When the report shows both the timeline total and the project-hour total
    Then either the two totals match
    Or the report shows a one-line note attributing the difference to
      minimum-session/rounding effects
```

- acceptance: a test that reproduces the gap from fixture sessions and asserts
  the chosen outcome (reconciled totals, or a rendered reconciliation note with
  the delta). First deliverable is the root-cause confirmation (GO/NO-GO on
  "flooring is the cause").
- validation: fixture-based test; manual re-run of the observed scenario.
- dependencies: `core/project_hours.py`, `core/domain.py`
  (`session_duration_hours`), the timeline-total computation, output renderers.

---

## later

### One documented reconciliation invariant for the whole report

- priority: later
- problem: findings #1 and #2 are two instances of the same missing rule: the
  report never states that displayed components must reconcile with their totals,
  so each surface (terminal, PDF, narrative, truth payload) rounds on its own.
- user value: the class of "numbers don't add up" defects stops recurring as new
  breakdowns are added.
- acceptance: a short invariant in the terminal style guide / a shared rounding
  utility — "any displayed total equals the sum of its displayed components;
  headline totals across sections reconcile or are explained" — referenced by the
  output modules.
- validation: the documented invariant plus the shared helper adopted by #1.
- dependencies: builds on #1's helper.

## Open decisions before implementation

- **#1 rounding strategy:** largest-remainder apportionment vs rendering the total
  as the sum of the rounded parts vs showing one more decimal. Pick the one that
  reads calmest per `docs/product/terminal-style-guide.md`.
- **#2 root cause:** confirm per-project session flooring is the source of the
  timeline-vs-total gap before deciding reconcile-vs-footnote.
- **Scope of #1:** the invoice PDF is in scope (the split is billed) — confirm no
  downstream consumer depends on the current independent rounding.

## Issue plan (on approval)

Per the skill's issue-lifecycle rule, item #1 (`now`) and #2 (`next`) become
issues via `/docs-to-issues`; #3 stays an entry here until promoted. Set
`priority:now` / `priority:next` labels and reflect on Project 3 if the `project`
gh scope is available.
