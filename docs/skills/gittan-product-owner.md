# Skill: `gittan-product-owner`

Status: active skill  
Canonical home for the product-owner workflow described in
[`../specs/repo-agent-skills.md`](../specs/repo-agent-skills.md).

## Purpose

Turn a fuzzy product concern into an **ordered, behavior-ready backlog** that an
implementer can pick up. This skill **does not write code** — it produces
priorities, acceptance criteria, and scenarios, and names the decisions that must
be made before implementation.

Use it as a planning *role*: the main question is "what should be built first,
and why?" The output is ordered backlog items, Gherkin where useful, acceptance
criteria, risks, and non-goals.

## When to use

Run this skill — usually **before** implementation — when the request involves
uncertainty, competing ideas, source weighting, privacy, retention, calendar
behavior, menu-bar UX, or backlog ordering. Trigger examples:

- "prioritize this"
- "turn this into backlog"
- "should we build X before Y?"
- "write requirements"
- "what are the slices?"
- "use Gherkin where helpful"

## Canonical docs to read

- [`../product/vision-documents.md`](../product/vision-documents.md) — vision /
  scope hierarchy and precedence (read this first for product framing).
- [`../specs/behavior-contract-standard.md`](../specs/behavior-contract-standard.md)
  — how to write the Gherkin in backlog items.
- [`../specs/source-evidence-policy.md`](../specs/source-evidence-policy.md) —
  when the work touches sources/collectors (evidence roles, weighting).

- [`../task-prompts/task-traceability-template.md`](../task-prompts/task-traceability-template.md)
  — the `## Traceability` block every committed task spec must carry.

Policy (branches, safety, tests, PR language) lives in `AGENTS.md`; point to it,
don't restate it. In particular `AGENTS.md` §223 (*Task spec traceability —
required*) governs the deliverable below.

## Workflow

1. Read the relevant product hierarchy docs.
2. Identify the user problem, trust/privacy constraints, and current repo policy.
3. Split work into small backlog items.
4. Mark each item `now`, `next`, `later`, or `do not build yet`.
5. Add Gherkin only where behavior needs shared understanding — not for every
   tiny internal task.
6. Include acceptance criteria and validation evidence for each `now` item.
7. Name dependencies and decisions needed before implementation.
8. **Commit the backlog as the deliverable** (see below) — a local working/
   plan-mode draft is not the artifact.

## Deliverable: a committed, traceable task-prompt (required)

The backlog **is** the deliverable, and it must land in the repo so the team,
the PRs, and tooling can see it:

- Write it to **`docs/task-prompts/<slug>-task.md`** (`AGENTS.md` §105–106),
  using [`../task-prompts/task-traceability-template.md`](../task-prompts/task-traceability-template.md).
- Include a `## Traceability` block (`AGENTS.md` §223): `story_id`,
  `spec_status`, `implementation_status`, `implementation.pr`, `changelog`, etc.
- A local plan-mode file is a **working draft only** — never leave the backlog
  there as the final state; copy it into the committed spec.
- **Implementing PRs must link to the spec** and update `implementation_status` /
  `implementation.pr` as work lands.

### Issue lifecycle (Story ID)

A `story_id: GH-N` is a real GitHub issue — the tracker for the spec. Keep it
disciplined so the issue list stays a trustworthy view of active work:

- **Create the issue when work starts — not when an item is prioritized.**
  Prioritization belongs in the spec and in labels; an issue is a *work record*,
  opened by whoever picks the item up. Agents (CodeRabbit/Cursor) should not
  auto-open issues either.

  This reverses the earlier rule ("create the issue when prioritized to
  `now`/`next`"), which was measured on 2026-08-18 and found to manufacture
  backlog rather than track it:

  | Measure | Value |
  | --- | --- |
  | Open issues that were planning/meta artifacts | 14 of 55 (25%) |
  | Median age of an open issue | 41 days (35 of 55 older than 30d) |
  | Median time-to-close | **0 days** — 49 of 80 closed the same day |

  The distribution is bimodal: an issue either closes the same day, because it
  was opened by someone already doing the work, or it sits for six weeks. There
  is almost nothing in between. Issues opened at *prioritization* time land in
  the second group, and a bulk import from specs put 8 of them there in one
  batch. Nothing was lost by parking them, because every one had a spec.

  The spec is the durable artifact and carries the acceptance criteria, the
  evidence and the priority. An issue adds a queue entry, and a queue nobody
  drains is a cost, not a record.
- **The implementing PR closes the issue** with `Closes #N`, so shipped work never
  leaves a straggler open (the failure seen in #145/#146).
- One issue per task-prompt; if a review spins off a follow-up, file it through the
  backlog (promote → issue), not as an ad-hoc duplicate.

This is enforced retrospectively by the feature-inventory generator's `--check`
(see `docs/task-prompts/feature-inventory-generator-task.md`): a command or
collector with no linked spec fails the gate. CodeRabbit cannot catch a *missing*
spec (it reviews the diff), so this discipline is on the planner. (Lesson: the
reported-time layer shipped in #186/#187 with the backlog only in a local plan
file and no traceable spec link — exactly what this section prevents.)

## Prioritizing the issue backlog (project board)

Specs become issues, and this skill **prioritizes the issues** — the board is the
live, ordered view.

This is consistent with the *Issue lifecycle* rule above, once you hold one model
of what a task-prompt is: **a `docs/task-prompts/*.md` file is a promoted (`now` /
`next`) spec.** Ideas that are `later` / `do not build yet` live as backlog
*entries inside* a spec (or in idea docs), **not** as their own task-prompt file.
So "one issue per task-prompt" and "only `now`/`next` items get issues" are the
same rule, not two — the generator only ever sees already-promoted specs.

- **Do not open an issue as part of this pass.** Priority lives in the spec and
  (for issues that already exist) in labels. When someone starts the work, they
  open the issue then — one issue, opened by the person doing the thing.
- *(Legacy, for an explicit backfill only)* **Create issues from specs with the generator**, not by hand: `/docs-to-issues`
  ([`docs-to-issues.md`](docs-to-issues.md)) turns each `docs/task-prompts/*.md`
  spec (already `now`/`next` by the rule above) into an issue idempotently (title +
  Traceability + Gherkin acceptance criteria). It skips specs whose
  `implementation_status` is already done. Dry-run, review, `--apply`. Re-runs never
  duplicate.
- **Set priority on each issue** with a label — `priority:now` / `priority:next` /
  `priority:later` / `priority:do-not-build` — matching the backlog framework above.
  Labels are the source of truth and work with the plain `repo` gh scope. (A demoted
  spec keeps its issue but takes a `later` / `do-not-build` label rather than being
  deleted.)
- **Reflect priority + status on the board** (GitHub Project 3,
  https://github.com/users/mbjorke/projects/3): add the issue and set its `Priority`
  / `Status` fields. Board writes need the `project` gh scope
  (`gh auth refresh -s project`); without it, keep priority in labels and add to the
  board once the scope is granted. The board is a **human view** — nothing reads its
  fields back, and **hosted** agent sessions cannot read it at all (local `gh` with
  `project` scope can write). A pass is complete once the labels are right. See
  [`../decisions/backlog-priority-surfaces.md`](../decisions/backlog-priority-surfaces.md).
- **The product-owner pass owns priority.** Promotion to a committed task-prompt is
  what makes an idea eligible for an issue; the pass then sets `now`/`next` vs a
  parking label. Re-run the prioritization when scope shifts — labels and board
  fields are cheap to move.

Flow: **fuzzy ask → promote to spec (task-prompt) → prioritized via labels on
the spec (this skill) → issue opened when someone starts the work.**

`/docs-to-issues` therefore stops being part of the planning pass. It remains
useful for a deliberate, reviewed backfill, but running it to "sync" specs into
issues recreates exactly the pattern measured above.

## Backlog item shape

````md
### <short title>

- priority: now | next | later | do not build yet
- problem:
- user value:
- non-goals:
- behavior:

```gherkin
Scenario: ...
```

- acceptance:
- validation:
- dependencies:
````

**Use Gherkin** when the behavior is: visible to users; safety/privacy/trust-
sensitive; a source/collector policy; a state machine or permission flow; likely
to be implemented by several tools/agents; or easy to misread in prose.

**Avoid Gherkin** for: a pure typo/doc routing fix; a mechanical rename; an
internal-only refactor with no behavior change; or anything already covered by an
existing behavior contract.

## Validation checklist

- [ ] Every item has a priority (`now` / `next` / `later` / `do not build yet`).
- [ ] `now` items have acceptance criteria and a validation note.
- [ ] User-visible or trust-sensitive items include a Gherkin scenario.
- [ ] Non-goals and open decisions/dependencies are named.
- [ ] No code was changed — output is a backlog, not an implementation.
- [ ] The backlog is committed to `docs/task-prompts/` with a `## Traceability`
      block — not left only in a local plan-mode file.
- [ ] Implementing PRs link back to the spec and keep `implementation_status`
      current.
- [ ] **No issue was opened by this pass.** An issue is opened when work starts,
      by whoever starts it — see *Issue lifecycle*.

## Behavior Contract

```gherkin
Feature: Product-owner planning skill
  Fuzzy product concerns become an ordered, behavior-ready backlog before code.

  Scenario: Product owner skill creates behavior-ready backlog
    Given the user describes a fuzzy product concern
    When the product owner skill is used
    Then the agent should produce ordered backlog items
    And user-visible or trust-sensitive items should include Gherkin scenarios
    And implementation should remain out of scope until priorities are clear

  Scenario: A planning pass does not manufacture issues
    Given a product-owner planning pass has ordered a backlog
    When the pass finishes
    Then the priorities are recorded in the committed spec
    And no new issue is opened for an item that nobody has started
    And an issue is opened only when someone begins the work

  Scenario: The backlog lands as a committed, traceable spec
    Given a product-owner planning pass has produced a backlog
    When the pass is finished
    Then the backlog is committed to docs/task-prompts/ as a task spec
    And it includes a Traceability block per AGENTS.md §223
    And it is not left only in a local plan-mode file
```
