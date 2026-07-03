# Task Prompt: Shadow log config default — durability must not depend on a per-run flag

## Traceability

- story_id: `GH-274`
- spec_status: `approved`
- implementation_status: `built`
- created_at: `2026-07-02`
- last_updated_at: `2026-07-02`
- implementation.pr: PR closing GH-274 (task/shadow-log-config-default)
- implementation.branch: `task/shadow-log-config-default`
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - `2026-07-02: Initial spec from the empty-evidence-store finding (issue #274); maintainer prio-steer: high, but next — not same-day.`
  - `2026-07-02: Items 1–2 built (config precedence + doctor row); re-prioritized to now in the post-0.3.0 planning pass.`

## Problem

The evidence shadow log (`core/evidence_store.py`, GH-151 slice 1) shipped as a
per-invocation CLI flag (`--shadow-log on`) defaulting **off**. On 2026-07-02 the
maintainer discovered `~/.gittan/evidence` was **empty** — no run had ever passed
the flag, while months of source history (Cursor/Claude logs, browser history)
had already rotated away unguarded. The maintainer's mental model — "gittan is
saving my evidence" — was the correct product design; the implementation assumed
a user who never forgets a flag. A same-day recovery run captured **13,156
records** (2026-03..07), but future runs again capture nothing without the flag.

A durability feature that must be remembered per run protects nobody. This is
invoice-evidence infrastructure: decayed evidence weakens every downstream
accuracy feature (evidenced-hours band GH-146, work-unit attribution GH-222).

## Backlog

### 1. Config-persistent shadow-log enablement

- priority: next
- problem: capture is per-run opt-in; forgetting the flag silently forfeits evidence.
- user value: turn it on once; every report/status run appends durable evidence.
- non-goals: changing the privacy stance (still opt-in — but opt-in **once**);
  capturing anything new beyond what `--shadow-log on` already captures; remote
  sync of the store.
- behavior:

```gherkin
Scenario: Shadow log enabled via config captures on every run
  Given the user has enabled the shadow log persistently in local config
  When any report or status run executes without a --shadow-log flag
  Then new observed evidence is appended to ~/.gittan/evidence
  And the run summary shows the shadow-log capture line

Scenario: CLI flag still overrides per run
  Given the shadow log is enabled in config
  When the user runs a report with --shadow-log off
  Then no evidence is captured for that run
```

- acceptance:
  - A setting in local config (e.g. `"shadow_log": "on"` in
    `timelog_projects.json` or a `~/.gittan` settings file — implementer picks the
    seam `core/config.py` already loads) enables capture for all report/status runs.
  - Precedence: explicit CLI flag > config > default off.
  - Quiet/JSON runs keep today's behavior (never touch `~/.gittan` implicitly)
    unless the config explicitly opts in — decide and document in the PR.
- validation: unit test for precedence; CLI smoke run with config on shows the
  capture line; `~/.gittan/evidence` record count grows.
- dependencies: none (evidence store already shipped).

### 2. Doctor surfaces evidence durability state

- priority: next
- problem: nothing warns that evidence is decaying while the shadow log is off.
- user value: `gittan doctor` makes the risk visible before months are lost.
- behavior:

```gherkin
Scenario: Doctor warns when the shadow log is off
  Given the shadow log is not enabled
  When the user runs gittan doctor
  Then a row warns that evidence decays with source-log rotation
  And it names the config setting that enables capture

Scenario: Doctor confirms when the shadow log is on
  Given the shadow log is enabled in config
  When the user runs gittan doctor
  Then a row shows shadow log on with record count and last-capture time
```

- acceptance: doctor row in both states; wording follows
  `docs/product/terminal-style-guide.md` (calm, no alarm-red for the off state —
  it is a recommendation, not an error).
- validation: doctor smoke run in both states.
- dependencies: item 1 (the config setting must exist to point at).

### 3. Periodic capture guidance (do not build yet)

- priority: do not build yet
- problem: even with config-on, capture only happens when the user runs a report;
  a quiet week still decays evidence.
- why parked: a background daemon/launchd job is a consent-and-footprint decision
  (see the 2026-07-01 launchd/persistence classifier refusal); revisit only after
  item 1 ships and real decay-between-runs is observed.

## Open decisions (named, not blocking item 1)

- Which config seam: `timelog_projects.json` vs a separate settings file.
  Leaning `timelog_projects.json` (one file, already backed up by tooling), but
  the projects config is also shared/committed in some flows — the implementer
  should confirm no privacy leak before choosing.
- Whether quiet/JSON runs should honor config-on (extension runs could then
  capture too) — default to **no** (preserve "never touch ~/.gittan implicitly")
  unless the maintainer opts in explicitly.

## Non-goals

- No change to what is captured or retention policy.
- No background scheduling (item 3 parked).
- No remote/cloud storage — the store stays local-first.

## Validation checklist

- [ ] Precedence unit test (flag > config > default) green.
- [ ] Smoke: config on → report run shows capture line; evidence count grows.
- [ ] Smoke: `--shadow-log off` suppresses capture despite config on.
- [ ] Doctor shows the correct row in both states.
- [ ] Incident cross-link: `docs/incidents/2026-07-01-observed-cache-overwrite-degrades-closed-months.md` references this spec as the durability follow-up.
