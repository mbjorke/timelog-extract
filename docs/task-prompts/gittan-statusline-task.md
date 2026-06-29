# gittan in the agent — statusline

## Context

gittan's time-tracking should be visible **inside the agent surfaces** where the
work happens (Claude Code, GitButler). The statusline composes a few signals;
each slice ships independently. The first actionable signal is a warning when the
current repo isn't set up — that is *why* time later can't auto-report.

A statusline runs on every prompt refresh, so it must be cheap: it **cannot run
collectors**. S1 is pure config + git-remote read; S2 depends on a cheap observed
cache that report runs persist as a byproduct.

## Phased backlog

### S1 — unconfigured-project warning
- priority: **built** — this PR (story GH-207)
- problem: when you work in a repo gittan has no profile for, time goes
  uncategorized silently. Warn in the agent so you fix it up front.
- scope: `scripts/gittan_statusline.py` (a dev script, not a `gittan` command):
  resolve the repo slug from cwd (`core/repo_slug.py::resolve_path_repo_slug`),
  match it against enabled `timelog_projects.json` profiles
  (`core/domain.py::classify_project`), and print one line. Fully defensive — any
  error prints blank so the prompt is never disrupted. Runbook:
  `docs/runbooks/gittan-statusline.md`.
- behavior:
  ```gherkin
  Scenario: Unconfigured repo warns
    Given the current repo's slug matches no profile in timelog_projects.json
    When the statusline runs
    Then it prints "⚠ gittan: project not set up · gittan map"

  Scenario: Configured repo is quietly confirmed
    Given the current repo matches a configured project
    Then it prints "gittan: <project>"

  Scenario: Not a git repo stays silent
    Given the working directory has no git remote
    Then it prints nothing (no false warning)
  ```
- acceptance: warning when no profile matches; `gittan: <name>` when matched;
  blank when no slug or on any error; cwd read from the statusline stdin JSON
  (`workspace.current_dir`) with a cwd fallback. Tests on the pure
  `project_status(slug, profiles)` (no git/network); full suite green; no file
  > 500 lines.
- non-goals: the unreported-hours number (S2); per-project observed cache (Part A).

### S2 — unreported-time nudge
- priority: **built** — PR #214 (story GH-213)
- problem: after `gittan report`, users still need a visible backlog of hours not
  yet triaged via `gittan reported`.
- scope: `⏱ Nh unreported · gittan reported` where
  `unreported = observed − handled` for today. Reads the observed cache (Part A)
  and the reported store (`core/reported_time.py::reported_hours_by_project_day`).
  All-clear: `✓ all reported today`; defensive blank on errors (same as S1).
- dependencies: Part A (merged #210).
- acceptance: composed statusline shows unreported nudge or all-clear for configured
  projects; S1 paths unchanged for unconfigured / non-git; tests in
  `tests/test_statusline.py`; collector-free (JSONL reads only).

### Part A — observed cache (enables S2)
- priority: **built** — merged #210
- scope: on report runs (`core/report_service.py`, where `overall_days` hours are
  known), persist a lightweight per-project-day observed summary to
  `~/.gittan/observed/YYYY-MM.jsonl` (mirrors `core/reported_time.py`
  conventions). Reuses already-computed hours; no new scan. The statusline reads
  this cache instead of running collectors.
- validation: `core/observed_cache.py`, `tests/test_observed_cache.py`, CI on #210.

## Decisions

- Statusline is a **dev script**, not a `gittan` end-user command (planning/dev
  tooling lives in `scripts/`).
- S1 stays **collector-free** (config + git-remote only) so it is safe per
  prompt refresh; the cache-backed number is S2/Part A.
- Quiet by default: warn only when action is needed; matched repos get a compact
  confirmation, non-git dirs print nothing.

## Traceability

- story_id: GH-207 (S1), GH-213 (S2)
- spec_status: approved
- implementation_status: built — S1 merged (#208); Part A merged (#210); S2 on PR #214
- created_at: 2026-06-29
- last_updated_at: 2026-06-29
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/208 (S1), https://github.com/mbjorke/timelog-extract/pull/210 (Part A), https://github.com/mbjorke/timelog-extract/pull/214 (S2)
- implementation.branch: task/statusline-unconfigured-warning (S1), task/observed-cache (Part A), task/statusline-unreported (S2)
- implementation.commits: [5c778bc] (S2)
- validation.evidence: `scripts/gittan_statusline.py`, `tests/test_statusline.py`, `core/observed_cache.py`, `tests/test_observed_cache.py`, `docs/runbooks/gittan-statusline.md`, CI on PR #214
- validation.decision: conditional GO — S2 pending merge/CI on #214
- changelog:
  - 2026-06-29: S1 built — collector-free statusline warning for an
    unconfigured project; runbook + tests. First visible "gittan in the agent"
    slice; auto-reporting (reported-time Phase 2b, #190) is the substrate that
    keeps the later unreported number (S2) quiet.
  - 2026-06-29: Part A built — observed cache merged via #210; enables S2 without
    collectors on prompt refresh.
  - 2026-06-29: S2 built — unreported-time nudge on `task/statusline-unreported`,
    PR #214 (Closes GH-213); closes the report → statusline → reported loop.
