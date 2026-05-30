# Behavior Contract Standard

Status: draft standard  
Last updated: 2026-05-29

## Purpose

Use lightweight Gherkin to make expected behavior readable before code is moved
or new features are built.

This standard does not require replacing `unittest`. It defines how specs should
describe behavior so existing and future tests can be mapped to product intent.

## When To Use

Add a `## Behavior Contract` section when a doc introduces or changes:

- user-visible CLI behavior,
- source collection or weighting,
- data safety / privacy behavior,
- path resolution,
- output schema or truth payload contracts,
- deprecations or command migrations,
- workflows intended for agents or automation.

Use Gherkin selectively. It is most valuable when the behavior is visible,
trust-sensitive, privacy-sensitive, stateful, or likely to be implemented by
multiple agents/tools. Do not force it onto tiny mechanical edits.

Small typo fixes and purely internal refactors do not need new Gherkin unless
they affect a behavior contract.

## Standard Shape

````md
## Behavior Contract

```gherkin
Feature: Short feature name
  One or two lines explaining the user value.

  Background:
    Given shared preconditions

  Scenario: Observable behavior in user language
    Given ...
    When ...
    Then ...
```

## Acceptance Criteria

- Each scenario has automated coverage or a documented manual verification note.
- Error and disabled states are explicit.
- Privacy and local-first behavior are stated when relevant.
````

## Style Rules

- Write scenarios in user/product language first, implementation language second.
- Prefer observable outcomes: CLI output, JSON keys, file writes, status rows,
  collector status, or no write.
- Keep one behavior per scenario.
- Avoid scenario names that merely restate a function name.
- Use neutral fixture names such as `Project Alpha`, `customer-a.test`, or
  `example.test`.
- Label compatibility-only behavior when testing deprecated surfaces.

## Test Mapping

Existing tests can map to scenarios without changing test framework:

```py
def test_explicit_worklog_path_wins(self):
    """Scenario: Explicit worklog path wins."""
```

For broader features, add a short mapping table in the spec:

| Scenario | Evidence |
| --- | --- |
| Explicit worklog path wins | `tests/test_source_strategy.py` |
| Missing Calendar permission disables source | pending |

## Compatibility Scenarios

Deprecated behavior may still need tests, but those scenarios should say why:

```gherkin
Scenario: Deprecated triage-map alias stays read-only during compatibility window
  Given the user runs "gittan triage-map --json"
  When the command completes
  Then it should not write project config
  And it should point users toward "gittan review"
```

This prevents compatibility tests from being mistaken for future design.

## Validation Levels

| Level | Use for | Evidence examples |
| --- | --- | --- |
| Unit | Pure logic and small helpers. | `python3 -m unittest tests.test_config_compat` |
| Integration | CLI wiring, collector registry, JSON payload shape. | `CliRunner`, subprocess tests, fixture runs. |
| Acceptance | User-visible scenario across modules. | Scenario-named tests, golden fixtures, smoke scripts. |
| Manual / demo | Workflows hard to automate safely. | Asciinema expected-outcome loop, runbook evidence. |

## Refactor Rule

Before a broad refactor, write or identify behavior contracts for the active
behavior being preserved. Deprecated behavior can keep narrow regression guards,
but should not define the target architecture.

## Backlog Rule

When a product-owner style task produces backlog, use Gherkin for `now` items
whose behavior must be shared across humans and agents. For `later` items, a
plain problem statement plus acceptance notes is usually enough until the item
moves closer to implementation.
