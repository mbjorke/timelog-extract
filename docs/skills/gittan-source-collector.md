# Skill: `gittan-source-collector`

Status: active skill  
Canonical home for the source-collector workflow described in
[`../specs/repo-agent-skills.md`](../specs/repo-agent-skills.md).

## Purpose

When adding or changing a data source, force the questions that are easy to skip
and expensive to retrofit: **source role, consent/permission, `collector_status`,
doctor visibility, tests that don't read live data, and retention**. The goal is
a new source that behaves like the existing ones, not a one-off.

A collector produces **evidence, not truth by itself**. Decide its role before
writing code (see the evidence policy below).

## When to use

Trigger: "add a source", "wire up <X> as a collector", "read <app>'s history /
database", "why is source <X> showing no events?", or any change under
[`../../collectors/`](../../collectors/).

## Canonical docs to read

- [`../specs/source-collector-contract.md`](../specs/source-collector-contract.md)
  — minimum collector behavior, enablement modes, date-window/event/status/doctor
  contracts, and the acceptance checklist.
- [`../specs/source-evidence-policy.md`](../specs/source-evidence-policy.md) —
  evidence roles (`primary_claim` … `scheduled_context` … `coverage_comparator`)
  and weighting; pick the role first.
- [`../sources/sources-and-flags.md`](../sources/sources-and-flags.md) — how
  collectors merge, source toggles vs `--exclude`, and `collector_status` in JSON.

Policy (branches, safety, tests, PR language) lives in `AGENTS.md`.

## Workflow

1. Confirm branch/status (`git branch --show-current`; `task/*` per `AGENTS.md`).
2. Read the source collector contract and the source evidence policy.
3. Identify the **source role** and **retention posture** (does its upstream log
   rotate? does it need the shadow log?).
4. Add a `## Behavior Contract` (Gherkin) to the spec/doc **before** implementation.
5. Implement to the contract; validate with **targeted tests** (fixtures, no live
   user data) plus the repo gate when code changes.

## Acceptance checklist

From [`../specs/source-collector-contract.md`](../specs/source-collector-contract.md):

- [ ] Source declares its **role** (per the evidence policy) before code lands.
- [ ] Event shape is `source` / `timestamp` / `detail` / `project`; extra
      provider metadata uses namespaced/private fields.
- [ ] Enablement mode behaves correctly (`off` reads nothing; `auto` fails closed
      with a reason; `on` reports clearly when prerequisites are missing).
- [ ] Date window: reads/filters only the requested window; no hidden "today".
- [ ] `collector_status` distinguishes disabled-by-setting, disabled-missing-prereq,
      enabled-zero-events, enabled-with-events, and error.
- [ ] Doctor row covers config/permission presence, mode, and next action in a
      maintained doc (not `docs/legacy/`), without printing secrets.
- [ ] Tests do **not** read live user data (mock/fixture).
- [ ] Privacy/redaction and shadow-log eligibility are stated.
- [ ] CLI-facing changes run the CLI impact smoke loop.

## Behavior Contract

```gherkin
Feature: Source-collector discipline
  New or changed sources follow one contract instead of copying one-off patterns.

  Scenario: Source collector work triggers source policy
    Given the user asks to add a new source
    When the source collector skill is used
    Then the agent should identify the source role
    And the agent should cover collector status, doctor behavior, privacy, tests, and retention
```
