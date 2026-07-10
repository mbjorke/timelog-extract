# Desirability pass — 2026-07-10 (product-owner)

A separate planning pass that asks the question a code-inward blind-spot pass
structurally cannot answer: **what stops a real, non-specialist user from getting
value from Gittan today, and what would make someone adopt and love it?** No code
is changed here — this is the ordered, behavior-ready backlog and the reasoning
behind it.

**Why a separate pass.** The blind-spot pass
(`blind-spot-pass-2026-07-10-task.md`) optimized for *not being wrong*. But
Gittan's product soul #5 is **"Practical over perfect — better weekly confidence
now beats theoretical completeness later,"** and the vision's aspirational
audience is *"anyone who has wished for automatic time reporting."* A perfectly
correct invoice tool that only a terminal specialist can configure serves almost
nobody. Desirability is the bottleneck to that audience, and it lives in the
**user's** territory — so this pass is grounded in the vision plus a real
first-run observation, not in code correctness.

**Decision filter for this pass (from `docs/product/gittan-vision.md`):** does
the change move Gittan from *specialist-only* toward *"anyone who wished for
automatic time reporting"* — by reducing cognitive load (soul #3) and delivering
review-ready value fast (north star: *"from scattered traces to trusted work
truth"*) — without breaking trust/local-first?

## Traceability

- story_id: `pending` (issues created on approval via `/docs-to-issues`)
- spec_status: `draft`
- implementation_status: `not built` (planning artifact — no code)
- created_at: `2026-07-10`
- last_updated_at: `2026-07-10`
- implementation.pr: pending
- implementation.branch: `claude/codebase-unknowns-el498z`
- implementation.commits: []
- validation.evidence: this backlog + first-run observation below
- validation.decision: `GO` (as a planning deliverable)
- changelog:
  - `2026-07-10: Initial desirability pass; first-run friction observed live.`

## Observed first-run (the evidence this pass is built on)

Run on a clean checkout, no `timelog_projects.json`, no `TIMELOG.md`:

- `gittan --today` (the command documented in `CLAUDE.md` and the instinctive
  first thing to type) → **red error box: `No such option: --today`.** The report
  moved under a `report` subcommand; the map (docs, muscle memory) and the
  territory (CLI) have diverged on *the very first command a new user types*.
- `gittan report --today` → runs, but with **no config it invents
  `default-project`**, prints a `~/Library/Mail not found` warning, and leads the
  output with trust caveats and process vocabulary (`observed → classified →
  approved`, *"Review before sharing, syncing, or invoicing"*) before delivering
  any *"here is your day."*
- `gittan setup` **does** exist ("one-click onboarding … and a first smoke
  report") — but nothing routes the new user to it. The golden path is not the
  discovered path.

Net: **time-to-first-value is currently time-to-first-error**, and even the happy
path leads with caveats over value. That is the adoption leak, and most of it is
nearly free to fix.

## Ordering at a glance

| # | Item | Moves specialist→anyone? | Priority |
| - | ---- | ------------------------ | -------- |
| D1 | First command doesn't error — `gittan --today` works or redirects | Directly (first 30 seconds) | **now** |
| D2 | First run leads with value, caveats second | Directly (the "wow") | **now** |
| D3 | Empty state routes the user into `setup` | Directly (find the golden path) | **next** |
| D4 | Lower the `timelog_projects.json` config cliff (non-LLM slice) | Directly (bet #3, named high-priority) | **next** |
| D5 | Reach beyond the terminal (GUI/aspirational audience) | Biggest reach, biggest risk | **do not build yet** |

---

## now

### First command never dead-ends

- priority: now
- problem: `gittan --today` — documented in `CLAUDE.md` and the natural first
  guess — errors with `No such option: --today` now that reporting lives under
  `report`. A brand-new user's first interaction is a red error box, not a
  result. This is the cheapest, highest-leverage desirability fix in the repo.
- user value: The first thing a curious person types produces a result (or a
  friendly redirect), not a failure. First impressions are the funnel.
- non-goals:
  - Do not remove the `report` subcommand or restructure the whole CLI.
  - Do not change report semantics or billing.
- behavior:

```gherkin
Feature: The first command a new user types does not dead-end
  Common first invocations produce a result or a helpful redirect, never a bare
  "No such option" error.

  Scenario: Legacy top-level report flags
    Given a user runs "gittan --today"
    When the CLI parses the arguments
    Then it either runs the report for today
    Or it prints "did you mean 'gittan report --today'?" and offers to run it
    And it never exits with only a "No such option: --today" error

  Scenario: Bare command invites onboarding
    Given a user runs "gittan" with no config present
    When the CLI has nothing to report
    Then it points the user to "gittan setup" as the first step
```

- acceptance: `gittan --today` (and other documented legacy top-level flags) no
  longer produce a bare parse error; `CLAUDE.md` / help text and the actual CLI
  agree on the entry command; a bare `gittan` with no config nudges toward
  `setup`.
- validation: CLI test asserting the redirect/behavior for `--today`; manual run
  on a clean checkout. Also fix the stale smoke command in `CLAUDE.md`.
- dependencies: `core/cli_app.py` (callback), `core/cli.py`, help text, `CLAUDE.md`.

### First run leads with value, not caveats

- priority: now
- problem: The empty/first report foregrounds warnings, trust disclaimers, and
  pipeline vocabulary before showing the user anything about *their* day. Souls
  #3 ("reduce cognitive load") and #5 ("practical over perfect") argue the
  opposite ordering: show "here's what you did today," then the caveats and the
  review-before-invoicing framing. Trust is a feature (#4) — but a caveat the
  user can't yet contextualize is noise, not trust.
- user value: The first run feels like a helpful summary, not a compliance form.
  That is the difference between "oh, nice" and "too much admin" (the exact pain
  the vision names).
- non-goals:
  - Do not weaken the trust guarantees — keep "not approved for invoice until
    reviewed" present, just not *first*.
  - Do not hide genuine access errors; demote expected-absence warnings
    (e.g. `~/Library/Mail not found` on a machine without Mail) to a quiet line.
- behavior:

```gherkin
Feature: Value-first first run
  A new user's first report leads with what they did, and frames caveats as a
  footer, not a preamble.

  Scenario: First report on a machine with some signal
    Given a user runs their first report and at least one source has events
    Then the output leads with a per-project/day summary of activity
    And trust caveats and the observed→classified→approved framing appear after
    And expected-absence source warnings are shown quietly, not as alerts
```

- acceptance: the terminal report renders a value summary before the caveat
  block; expected-absence warnings are demoted; the output honors
  `docs/product/terminal-style-guide.md` (calm, low-noise).
- validation: golden/terminal-preview snapshot of a first-run report; review
  against the style guide.
- dependencies: `outputs/terminal.py`, `outputs/terminal_report_sections.py`,
  `outputs/terminal_warnings.py`, `outputs/narrative.py`.

---

## next

### Empty state routes into onboarding

- priority: next
- problem: `gittan setup` is real one-click onboarding, but a new user reaches it
  only if they already know to. `gittan` alone lists commands; `gittan report`
  with no config silently invents `default-project`. The golden path exists but
  isn't the discovered path.
- user value: Nobody gets stuck staring at `default-project` wondering why
  nothing is classified — the tool actively offers the next step.
- non-goals: do not auto-write config without consent (local-first / trust);
  offer, don't impose.
- acceptance: with no `timelog_projects.json`, `report` and `doctor` surface a
  one-line "run `gittan setup` to get accurate project hours" call-to-action;
  `setup` is discoverable from the empty state.
- validation: CLI test for the no-config nudge; manual clean-checkout walkthrough
  from `gittan` → `setup` → first real report.
- dependencies: builds on the shipped onboarding guidance (GH-197,
  `project-config-onboarding-guidance-task.md`); `core/cli_report_status.py`,
  `core/cli_doctor_sources_projects.py`.

### Lower the config cliff — non-LLM slice

- priority: next
- problem: Product bet #3 (opportunities.md, "High priority"): creating and
  maintaining `timelog_projects.json` is still specialist work, so classification
  is specialist-only. The AI-assisted-config vision
  (`docs/sources/ai-assisted-config.md`) is the north star, but its own phasing
  says **project names/buckets matter first** and shipping can start with
  **non-LLM simplifications**. Solopreneurs specifically need help *inventing*
  stable project labels from messy traces — the hardest part, and the one that
  needs no LLM.
- user value: A non-specialist gets usable project buckets in minutes without
  hand-authoring JSON, so their first real report is actually classified.
- non-goals:
  - No cloud LLM in this slice (that stays opt-in, later phase).
  - No exfiltration of activity — seed from git remotes / repo names / calendar
    codes the user already has locally (`map`, `calendar-suggest` exist).
- behavior:

```gherkin
Feature: Get usable project buckets without hand-writing JSON
  A first-time user ends up with named projects seeded from signals already on
  their machine, under explicit approval.

  Scenario: Seed projects from local signals
    Given a user with no timelog_projects.json runs onboarding
    When Gittan proposes project buckets from git remotes and repo names
    Then the user can approve, rename, or drop each proposed bucket
    And nothing is written to config without explicit approval
    And the resulting config validates against core/config.py normalize rules
```

- acceptance: onboarding proposes named buckets from local signals (leaning on
  existing `map` / `calendar-suggest` / `projects-audit`), with approve/rename/
  drop; output passes `normalize_profile` and `projects-lint`.
- validation: end-to-end onboarding test producing a valid config from fixture
  git remotes; manual run. Measure: does a fresh user reach a classified report
  without editing JSON by hand?
- dependencies: `core/cli_map.py`, `core/cli_calendar_suggest.py`,
  `core/setup_projects_config_bootstrap.py`, `core/config.py`; north star
  `docs/sources/ai-assisted-config.md`.

---

## do not build yet

### Reach beyond the terminal (aspirational GUI audience)

- priority: do not build yet
- problem: The vision's aspirational audience is *"anyone who has wished for
  automatic time reporting,"* but Gittan is terminal-only, which caps reach at
  dev/ops. A GUI/menu-bar surface is the biggest desirability *reach* — and the
  biggest scope and maintenance risk. Opportunities bet #2 is explicit: the
  Cursor/IDE extension is **not** the hero path and companion GUI may be
  **deprioritized or dropped** in favor of engine + terminal story.
- why not now: Building GUI parity before the CLI "wow" and the config cliff are
  solved would spend the solo maintainer's scarcest resource on the widest,
  riskiest surface. Practical over perfect: **deepen the CLI experience for the
  dev audience you actually have** (D1–D4) first; let real pull from that
  audience — not aspiration — justify a GUI later.
- what would promote it: evidence of adoption demand from non-terminal users
  that the CLI cannot satisfy, and a maintenance model that doesn't starve the
  engine.
- non-goals: no GUI/extension hero investment this cycle.

---

## The meta-unknown this pass cannot close

A blind-spot pass reads code; a desirability pass reads users — and **this pass
still only read the vision and one first-run, not real users.** The largest
desirability unknowns — *would the aspirational audience actually adopt? what do
target users truly value first?* — cannot be answered from the repo. The honest
next move alongside D1–D4 is to **watch 3–5 real first-runs** (or lightweight,
consent-based local first-run telemetry) and let observed behavior, not this
document's hypotheses, re-order the backlog. That is the same "map is not the
territory" discipline applied to desirability: the vision is the map; user
behavior is the territory, and we have not measured it yet.

## Issue plan (on approval)

Per the skill's issue-lifecycle rule, the two `now` items and two `next` items
become issues via `/docs-to-issues`; D5 stays an entry here until promoted. Set
`priority:now` / `priority:next` labels and reflect on Project 3 if the `project`
gh scope is available.

## Open decisions before implementation

- **D1:** redirect `--today` to `report --today`, or reinstate a top-level
  default report command? (Redirect is lower-risk; a default command is more
  ergonomic.) Also decide the fix scope for other legacy top-level flags.
- **D2:** exact split between "value" and "caveat" blocks — confirm against the
  terminal style guide before moving anything.
- **D4:** which local signals seed buckets by default (git remotes only, or also
  calendar codes / directory names), and the consent copy for each.
