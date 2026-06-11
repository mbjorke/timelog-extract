# Activity anchor signal

Status: built  
Last updated: 2026-06-11

> Originally the **working-directory** anchor signal; generalized to a multi-kind
> **activity anchor** model (`dir`, `branch`, `label`). The directory remains the
> first and strongest kind; the design and contract below cover all three.

## Problem

AI tools already classify by a structural anchor, not just message text.
`collectors/ai_logs.py::collect_claude_code` prepends the project directory name
(and now the git branch) to the event text before `classify_project`; Codex
classifies purely by `thread_name` (session title). This works **only if** a
project profile has a `match_term` that is a substring of that anchor. When the
config is incomplete, a full active session classifies as `Uncategorized` even
though the directory / branch / title unambiguously identifies the work.

The anchor was **discarded** historically: `make_event` stored only
`source`/`timestamp`/`detail`/`project`, so the anchor was lost after
collection. `projects-audit` therefore could not surface it, and there was no
material for an "add this as a match_term?" suggestion — the analogue of the
existing `top_hosts` suggestion for browser tools.

## The three anchor kinds

An event carries a namespaced `anchors` map (`{kind: value}`), per the
source-collector contract (extra provider metadata uses a private/namespaced
field, never `detail`). Each value is privacy-safe and already part of the
classification haystack for its source, so the same substring rule decides
whether a profile already anchors it.

| Kind | Value | Coverage | Notes |
| --- | --- | --- | --- |
| `dir` | working-directory leaf (basename) | Claude Code, Cursor, Windsurf, Antigravity, Gemini CLI | structured; strongest suggestion |
| `branch` | git branch leaf (after last `/`) | Claude Code (`gitBranch`) | namespace prefix dropped; generic branches (`main`, …) rejected |
| `label` | session title | Codex IDE (`thread_name`) | full-coverage signal; placeholders (`session`, …) rejected; trim before use as match_term |

Why three: `dir` exists only where there is a cwd; `branch` rides the same record
and is often more descriptive; `label` is the only kind with **full coverage**
across chat tools (every session has a title) — but it is free text, so it is a
weaker auto-suggestion than a path leaf. See
`docs/ideas/triage-signal-examples.md`.

## Scope

1. Preserve all anchors as a namespaced `anchors` map on the event. Values are
   privacy-safe: a `dir` leaf (`timelog-extract`) carries no home prefix or
   username (`/Users/<name>/…`); a `branch` leaf drops any namespace segment; a
   `label` is the title only.
2. `top_signals` aggregation in `projects-audit` (schema v2) — one unified model
   that folds the former `top_hosts` and `top_anchors`. Each row is
   `{kind, value, hits, anchored, rule_type}`: `kind=host` (web host from detail
   → `tracked_urls`) or `kind=dir/branch/label` (→ `match_terms`). `anchored` is
   true if a profile rule already covers the value (the same rules
   classification uses).
3. Suggestion/apply loop: `projects-audit --write-anchor-plan PATH` writes a
   reviewable plan of rule additions for unanchored signals (any kind, each
   tagged with `anchor_kind` and its own `rule_type`); `projects-anchor -i PATH
   [--dry-run]` applies it (with backup, `match_terms` or `tracked_urls`),
   mirroring the trim flow.
4. Automatic surfacing (modal wall): `status` shows a one-line warning when
   unmapped anchors carry real activity and — on an interactive TTY — offers to
   map them in place (questionary; `--no-anchor-nudge` opts out). `report`
   prints a richer multi-line nudge listing the anchors. `status` alerts;
   `report` explains. A React Ink overlay can replace the interactive surface
   later without changing the data contract.

Out of scope here: the React Ink overlay; auto-mapping an anchor to an existing
project (the plan/flow keep a human choice per anchor); per-source title
harvesting beyond Codex (Claude Code `~/.claude.json` history, web tab titles)
— a future `label`-coverage slice.

## Evidence role

An `anchors` value is **corroborating context**, not a primary claim. It does
not change classification; it preserves a signal already used at collection time
so it can be audited and suggested. Existing classification behavior is
unchanged.

## Behavior Contract

```gherkin
Feature: Activity anchor signal
  The structural anchors of an AI session (working directory, git branch,
  session title) are preserved as evidence and surfaced for match_term
  suggestions, without changing classification.

  Scenario: Claude Code CLI event preserves its working-directory leaf
    Given a Claude Code JSONL entry with cwd "/home/user/timelog-extract"
    When the Claude Code collector builds the event
    Then the event carries anchors.dir "timelog-extract"
    And the event detail is unchanged
    And no home prefix or username segment is stored

  Scenario: Claude Code CLI event preserves its git branch leaf
    Given a Claude Code JSONL entry with gitBranch "feature/project-beta"
    When the Claude Code collector builds the event
    Then the event carries anchors.branch "project-beta"
    And the namespace segment "feature/" is dropped

  Scenario: Generic branches carry no branch anchor
    Given a Claude Code JSONL entry with gitBranch "main"
    When the Claude Code collector builds the event
    Then the event has no branch anchor

  Scenario: Codex IDE event preserves its session title
    Given a Codex session with thread_name "Project Beta home redesign"
    When the Codex collector builds the event
    Then the event carries anchors.label "project beta home redesign"
    And a placeholder title "session" yields no label anchor

  Scenario: Audit surfaces unanchored anchors of any kind
    Given collected events carry an anchor value with no matching profile
    When projects-audit runs
    Then top_anchors includes that value with its kind and event count
    And that row is marked anchored=false

  Scenario: Anchored value is flagged
    Given a profile with a match_term that is a substring of an anchor value
    And events carry that anchor value
    When projects-audit runs
    Then the top_anchors row for that value is marked anchored=true

  Scenario: Anchor plan proposes match_terms for unanchored anchors
    Given projects-audit reports an unanchored anchor "timelog-extract"
    When projects-audit runs with --write-anchor-plan
    Then the plan contains a match_terms addition with value "timelog-extract"
    And the addition carries its anchor_kind
    And project_name defaults to "timelog-extract" for human review

  Scenario: Applying an anchor plan adds the match_term
    Given an anchor plan adds match_term "timelog-extract" to project "gittan"
    When projects-anchor applies the plan without --dry-run
    Then the project "gittan" gains the match_term "timelog-extract"
    And a config backup is written first

  Scenario: status warns about unmapped anchors
    Given activity from an anchor value with no matching profile
    And the events exceed the nudge threshold
    When status runs
    Then a one-line warning names the value, its kind, and its event count
    And on a non-interactive session the manual anchor commands are printed
    And --no-anchor-nudge suppresses the warning entirely

  Scenario: status maps an anchor interactively
    Given an interactive session and an unmapped anchor "timelog-extract"
    When the user confirms mapping and selects project "gittan"
    Then "gittan" gains the match_term "timelog-extract"
    And a config backup is written first
```

## Privacy

- `dir`: only the **leaf** is stored (basename), never the full path.
- `branch`: only the segment after the last `/`, dropping any namespace prefix.
- `label`: only the session title, truncated; placeholder titles are dropped.
- Absent an anchor, no entry is set (no fragile decoding of mangled names that
  could leak path segments). The `anchors` map is local, user-owned report data,
  omitted entirely when an event has no anchor, keeping the event shape additive.

## Related

- `docs/specs/source-collector-contract.md` — event shape + namespaced metadata.
- `docs/specs/source-evidence-policy.md` — corroborating-context role.
- `docs/ideas/triage-signal-examples.md` — why terminal events look weak in
  `detail` yet classify by directory, branch, or title.
- `docs/ideas/fast-project-mapping-playbook.md` — the manual mapping flow a
  `top_dirs`-driven suggestion would accelerate.
