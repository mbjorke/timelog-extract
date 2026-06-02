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

Policy (branches, safety, tests, PR language) lives in `AGENTS.md`; point to it,
don't restate it.

## Workflow

1. Read the relevant product hierarchy docs.
2. Identify the user problem, trust/privacy constraints, and current repo policy.
3. Split work into small backlog items.
4. Mark each item `now`, `next`, `later`, or `do not build yet`.
5. Add Gherkin only where behavior needs shared understanding — not for every
   tiny internal task.
6. Include acceptance criteria and validation evidence for each `now` item.
7. Name dependencies and decisions needed before implementation.

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
```
