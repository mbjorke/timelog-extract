# Repo Agent Skills

Status: draft spec  
Last updated: 2026-05-29

## Purpose

Define which reusable, tool-independent agent skills would help this repo
without duplicating `AGENTS.md`.

Skills should be small, procedural entry points for repeated work. They must be
portable across Cursor, Codex, Claude, Antigravity, and other agent surfaces.
They should point back to canonical repo docs instead of becoming a second
policy layer.

## Existing Policy

`docs/contributing/ai-assisted-work.md` currently says a repo-level `SKILL.md`,
if added, should be thin: a pointer to `AGENTS.md` and the test command, not a
parallel rulebook.

This spec keeps that direction. The useful move is not "one giant Gittan skill"
or a vendor-specific ruleset; it is a small set of portable playbooks that can
be adapted into each tool's skill/command/rule format.

## Portability Requirement

Repo skills must be vendor-neutral at the source.

- Canonical skill content should live in ordinary repo docs.
- Tool-specific wrappers may exist, but must point back to the canonical doc.
- Cursor commands, Claude skills, Codex skills, Antigravity prompts, and future
  tools should not diverge in policy.
- If a tool-specific wrapper cannot express the full workflow, it should say
  which canonical doc to read next.

## Candidate Skills

| Portable skill | Trigger | Purpose | Canonical docs to read |
| --- | --- | --- | --- |
| `gittan-docs-foundation` | deprecation inventory, behavior contracts, source policy docs | Keep docs-only foundation changes aligned with current policy. | `AGENTS.md`, `docs/decisions/deprecation-and-test-weakness-inventory.md`, `docs/specs/behavior-contract-standard.md` |
| `gittan-product-owner` | prioritization, backlog shaping, feature slicing, acceptance criteria | Turn fuzzy product concerns into ordered backlog items with Gherkin when behavior is user-visible or risky. | `docs/product/vision-documents.md`, `docs/specs/behavior-contract-standard.md`, `docs/specs/source-evidence-policy.md` when source-related |
| `gittan-source-collector` | adding or changing a source collector | Force source role, consent, `collector_status`, doctor, tests, and retention questions early. | `docs/specs/source-collector-contract.md`, `docs/specs/source-evidence-policy.md`, `docs/sources/sources-and-flags.md` |
| `gittan-timelog-health` | health monitor, menu bar, central worklog capture | Keep health, central per-project worklogs, and menu bar JSON separate from legacy repo-local `TIMELOG.md`. | `docs/specs/timelog-health-monitor.md`, `docs/runbooks/global-timelog-setup.md` |
| `gittan-shadow-log` | evidence retention, replay, snapshotting | Guide opt-in local evidence retention without cloud upload or raw-log overcollection. | `docs/specs/local-evidence-shadow-log.md`, `docs/specs/timelog-truth-standard-rfc.md` |
| `gittan-calendar-source` | Apple Calendar / Google Calendar planning or implementation | Keep Calendar as scheduled context unless the policy changes. | `docs/specs/source-evidence-policy.md`, `docs/specs/source-collector-contract.md` |

## Skill Roles

Portable skills can act like lightweight roles. A task may use more than one,
but the handoff should say which role is active.

| Role | Main question | Output |
| --- | --- | --- |
| Product owner | What should be built first, and why? | Ordered backlog, Gherkin scenarios where useful, acceptance criteria, risks, non-goals. |
| System designer | What contract or boundary makes this safe to build? | Specs, source/evidence policy, architecture notes, data contracts. |
| Implementer | What is the smallest safe code/docs change? | Scoped diff, tests, validation evidence. |
| Reviewer | What could break or become misleading? | Findings, gaps, missing tests, risk notes. |

The product-owner role should usually run before implementation when the request
contains uncertainty, competing ideas, source weighting, privacy, retention,
calendar behavior, menu bar UX, or backlog ordering.

## Product Owner Skill

`gittan-product-owner` should be the planning skill for fuzzy product work. It
does not write code. It creates a backlog that is ready for an implementer.

Trigger examples:

- "prioritize this"
- "turn this into backlog"
- "should we build X before Y?"
- "write requirements"
- "what are the slices?"
- "use Gherkin where helpful"

Workflow:

1. Read the relevant product hierarchy docs.
2. Identify the user problem, trust/privacy constraints, and current repo
   policy.
3. Split work into small backlog items.
4. Mark each item as `now`, `next`, `later`, or `do not build yet`.
5. Add Gherkin only where behavior needs shared understanding, not for every
   tiny internal task.
6. Include acceptance criteria and validation evidence for each `now` item.
7. Name dependencies and decisions needed before implementation.

Backlog item shape:

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

Use Gherkin when the behavior is:

- visible to users,
- safety/privacy/trust-sensitive,
- a source/collector policy,
- a state machine or permission flow,
- likely to be implemented by several tools/agents,
- easy to misread in prose.

Avoid Gherkin when the work is:

- a pure typo/doc routing fix,
- a mechanical rename,
- an internal-only refactor with no behavior change,
- already covered by an existing behavior contract.

## Behavior Contract

```gherkin
Feature: Portable repo agent skills
  Repeated agent tasks use concise, tool-independent skill entry points without forking repo policy.

  Scenario: A skill points to canonical policy
    Given an agent uses a Gittan repo skill from any supported tool
    When the skill needs branch, safety, or validation rules
    Then it should point to AGENTS.md
    And it should not restate long policy text

  Scenario: Tool-specific wrappers stay thin
    Given a Cursor command and a Claude skill support the same Gittan workflow
    When their instructions mention repo policy
    Then both should point to the same canonical repo doc
    And neither should introduce tool-only policy differences

  Scenario: Source collector work triggers source policy
    Given the user asks to add a new source
    When the source collector skill is used
    Then the agent should identify the source role
    And the agent should cover collector status, doctor behavior, privacy, tests, and retention

  Scenario: Product owner skill creates behavior-ready backlog
    Given the user describes a fuzzy product concern
    When the product owner skill is used
    Then the agent should produce ordered backlog items
    And user-visible or trust-sensitive items should include Gherkin scenarios
    And implementation should remain out of scope until priorities are clear

  Scenario: Timelog health work avoids legacy repo-local assumptions
    Given the user asks about health monitoring for time capture
    When the timelog health skill is used
    Then the agent should treat central per-project worklogs as the maintained model
    And repo-local TIMELOG.md should only be discussed as legacy fallback
```

## Canonical Skill Shape

Each portable skill should be concise:

- One canonical Markdown doc in the repo.
- A short workflow, trigger guidance, and validation checklist.
- Optional examples only when they reduce ambiguity.
- No copied `AGENTS.md` sections.
- No tool-specific assumptions in the canonical doc.

## Tool Wrapper Shape

Tool-specific wrappers are allowed when useful:

- Cursor slash commands.
- Claude/Codex `SKILL.md` files.
- Antigravity prompt snippets.
- Other agent-specific rule files.

They should be thin:

1. name the workflow,
2. point to the canonical repo skill doc,
3. list one or two tool-specific mechanics if needed,
4. avoid restating policy.

## Proposed First Skill

Start with the portable `gittan-product-owner` workflow, then
`gittan-source-collector`.

Reason:

- Product-owner planning helps decide whether Calendar, health, or shadow-log
  work comes first.
- Source-collector discipline then keeps actual integration work consistent.

`gittan-source-collector` minimum body:

Minimum body:

1. Confirm branch/status.
2. Read source collector contract and source evidence policy.
3. Identify source role and retention posture.
4. Add behavior contract before implementation.
5. Validate with targeted tests plus repo gate when code changes.

## Open Questions

- Where should canonical portable skills live: `docs/skills/`,
  `docs/runbooks/agent-skills/`, or `docs/specs/` while still draft?
- Should `.cursor/commands/`, Claude skills, Codex skills, and Antigravity
  snippets be generated from the same source later?
- Should a root `SKILL.md` remain a one-line pointer to `AGENTS.md`, or be
  avoided entirely until a tool explicitly benefits from it?
- How much tool-specific wrapper content is acceptable before it becomes a
  forked policy surface?
