# Working-directory anchor signal

Status: draft spec  
Last updated: 2026-06-11

## Problem

Terminal AI tools (Claude Code CLI, Cursor, Gemini CLI) already classify by
working directory: `collectors/ai_logs.py::collect_claude_code` prepends the
project directory name to the event text before `classify_project`. This works
**only if** a project profile has a `match_term` that is a substring of that
directory name. When the config is incomplete, a full active session classifies
as `Uncategorized` even though the directory unambiguously identifies the work.

The directory signal is **discarded** today: `make_event` stores only
`source`/`timestamp`/`detail`/`project`, so the working directory is lost after
collection. `projects-audit` therefore cannot surface it, and there is no
material for a "add this directory as a match_term?" suggestion — the
terminal-tool analogue of the existing `top_hosts` suggestion for browser tools.

## Scope (this slice)

1. Preserve the working-directory **leaf** as a namespaced event field
   (`context_dir`), per the source-collector contract (extra provider metadata
   uses a private/namespaced field, never `detail`).
2. Source it from the Claude Code JSONL `cwd` field (exact leaf via basename),
   which is privacy-safe: the leaf (`timelog-extract`) carries no home prefix or
   username (`/Users/<name>/…`).
3. Add `top_dirs` aggregation to `projects-audit`, analogous to `top_hosts`,
   with an `anchored` flag (true if any profile already matches the leaf).

4. Suggestion/apply loop: `projects-audit --write-anchor-plan PATH` writes a
   reviewable plan of match_term additions for unanchored dirs; `projects-anchor
   -i PATH [--dry-run]` applies it (with backup), mirroring the trim flow.
5. Automatic surfacing (modal wall): `status` shows a one-line warning when
   unmapped directories carry real activity and — on an interactive TTY — offers
   to map them in place (questionary; `--no-anchor-nudge` opts out). `report`
   prints a richer multi-line nudge listing the directories. `status` alerts;
   `report` explains. A React Ink overlay can replace the interactive surface
   later without changing the data contract.

Out of scope here: extending `context_dir` to Cursor/Gemini collectors
(follow-up), the React Ink overlay, and auto-mapping a directory to an existing
project (the plan/flow keep a human choice per directory).

## Evidence role

`context_dir` is **corroborating context**, not a primary claim. It does not
change classification; it preserves a signal already used at collection time so
it can be audited and suggested. Existing classification behavior is unchanged.

## Behavior Contract

```gherkin
Feature: Working-directory anchor signal
  The working directory of a terminal AI session is preserved as evidence and
  surfaced for match_term suggestions, without changing classification.

  Scenario: Claude Code CLI event preserves its working-directory leaf
    Given a Claude Code JSONL entry with cwd "/home/user/timelog-extract"
    When the Claude Code collector builds the event
    Then the event carries context_dir "timelog-extract"
    And the event detail is unchanged
    And no home prefix or username segment is stored

  Scenario: Audit surfaces unanchored working directories
    Given collected events carry context_dir "timelog-extract"
    And no profile has a match_term that is a substring of "timelog-extract"
    When projects-audit runs
    Then top_dirs includes "timelog-extract" with its event count
    And that row is marked anchored=false

  Scenario: Anchored directory is flagged
    Given a profile with match_term "timelog-extract"
    And events carry context_dir "timelog-extract"
    When projects-audit runs
    Then the "timelog-extract" top_dirs row is marked anchored=true

  Scenario: Anchor plan proposes match_terms for unanchored directories
    Given projects-audit reports an unanchored directory "timelog-extract"
    When projects-audit runs with --write-anchor-plan
    Then the plan contains a match_terms addition with value "timelog-extract"
    And project_name defaults to "timelog-extract" for human review

  Scenario: Applying an anchor plan adds the match_term
    Given an anchor plan adds match_term "timelog-extract" to project "gittan"
    When projects-anchor applies the plan without --dry-run
    Then the project "gittan" gains the match_term "timelog-extract"
    And a config backup is written first

  Scenario: status warns about unmapped directories
    Given activity from working directory "timelog-extract" with no matching profile
    And the events exceed the nudge threshold
    When status runs
    Then a one-line warning names "timelog-extract" and its event count
    And on a non-interactive session the manual anchor commands are printed
    And --no-anchor-nudge suppresses the warning entirely

  Scenario: status maps a directory interactively
    Given an interactive session and an unmapped directory "timelog-extract"
    When the user confirms mapping and selects project "gittan"
    Then "gittan" gains the match_term "timelog-extract"
    And a config backup is written first
```

## Privacy

- Only the directory **leaf** is stored (basename), never the full path.
- Absent `cwd`, no `context_dir` is set (no fragile decoding of mangled dir
  names that could leak path segments).
- The field is local, user-owned report data; it is omitted from events that
  have no directory context, keeping the event shape additive.

## Related

- `docs/specs/source-collector-contract.md` — event shape + namespaced metadata.
- `docs/specs/source-evidence-policy.md` — corroborating-context role.
- `docs/ideas/triage-signal-examples.md` — why terminal events look weak in
  `detail` yet classify by directory.
- `docs/ideas/fast-project-mapping-playbook.md` — the manual mapping flow a
  `top_dirs`-driven suggestion would accelerate.
