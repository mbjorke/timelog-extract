# Backlog: Post Gittan hours to Toggl (`gittan toggl-sync`)

Planning pass via the `gittan-product-owner` skill. Ordered, behavior-ready
backlog — implementation of the `now` item has started on `task/toggl-posting`
(see Traceability). Later items are not built.

## Product framing

Source of truth for this work is the **solo-first integration model**
([`docs/ideas/simple-invoicing-model.md`](../ideas/simple-invoicing-model.md)):
*export, do not expose; push-only connectors; draft-first writes; dry-run prints
the exact payload; idempotency keys; a local operation log with rollback/regret
recovery.* Toggl is the first named push target in
[`docs/ideas/conversational-ui-stack.md`](../ideas/conversational-ui-stack.md)
("Sync targets — Toggl first, Briox…").

The existing `collectors/toggl.py` read-collector points the *wrong* way (pull
*from* Toggl) and is an unimplemented placeholder; it is left untouched. This
backlog is about the **push** direction and mirrors the shipped `gittan
jira-sync` flow.

## Decisions needed before / during build

- **D1 — Project mapping home.** Toggl needs a numeric `project_id` per project.
  Decision: add an optional `toggl_project_id` to each profile in
  `timelog_projects.json`. (No git-commit analogue like Jira's issue key.)
- **D2 — Granularity.** Decision for `now`: one entry per **project + day**
  (matches `jira-sync`, gives a stable dedup key). Per-session is `later`.
- **D3 — Workspace.** Single default workspace for `now`
  (`--toggl-workspace-id` / `TOGGL_WORKSPACE_ID`). Multi-workspace is `later`.
- **D4 — Rollback.** Toggl supports `DELETE` on a time entry, so true rollback
  *is* possible — but it is scoped to the `next` item (operation log), not `now`.

---

### Toggl push MVP — `gittan toggl-sync`

- priority: **now** (in progress)
- problem: Gittan computes per-project/day hours but cannot push them to Toggl;
  the only Toggl code reads the wrong direction and is a placeholder.
- user value: Marcus posts confirmed hours to Toggl without manual re-entry, so
  Toggl reports/exports stay in sync from a single local source of truth.
- non-goals:
  - reading/importing time *from* Toggl (placeholder collector stays as-is)
  - per-session entries (project+day only)
  - multi-workspace fan-out
  - auto-creating Toggl projects (unmapped projects are surfaced, never created)
  - `reported_time` bridge integration
    ([`scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md) fase 4)
- behavior:

```gherkin
Feature: Post Gittan hours to Toggl as time entries
  Marcus pushes Gittan's computed project hours to Toggl so his reports
  stay in sync, with confirmation and duplicate protection.

  Background:
    Given TOGGL_API_TOKEN and a default workspace id are configured
    And timelog_projects.json maps "Project Alpha" to toggl_project_id 123456789

  Scenario: Aggregate per project and day
    Given Project Alpha has two sessions on 2026-06-23 totaling 2.5h
    When the user runs "gittan toggl-sync --from 2026-06-23 --to 2026-06-23 --dry-run"
    Then one candidate for Project Alpha on 2026-06-23 with 2.5h is shown
    And the exact outgoing payload is printed
    And no time entry is posted

  Scenario: Unmapped project is surfaced, never posted
    Given Project Beta has 1h on 2026-06-23 and no toggl_project_id
    When the user runs "gittan toggl-sync --from 2026-06-23 --to 2026-06-23"
    Then Project Beta is reported as unmapped
    And no time entry is posted for Project Beta

  Scenario: Duplicate protection on re-run
    Given a Toggl entry tagged "gittan:123456789:2026-06-23" already exists
    When the user runs "gittan toggl-sync --from 2026-06-23 --to 2026-06-23"
    Then the Project Alpha candidate for that day is skipped as a duplicate
    And the summary counts it under skipped

  Scenario: Confirm gate on interactive post
    Given a mappable candidate with no existing duplicate
    And require_confirm is on
    When the user declines the confirmation prompt
    Then no time entry is posted
    And the candidate is counted under skipped

  Scenario: Successful post
    Given a mappable candidate with no existing duplicate
    When the user confirms the post
    Then a time entry is created via POST /api/v9/workspaces/{id}/time_entries
    And it carries description, project_id, duration, and the gittan marker tag
    And the summary counts it under posted
```

- acceptance:
  - `gittan toggl-sync` exists and is registered in `core/cli.py`.
  - Candidates aggregate per project + day; durations match the `jira-sync`
    computation path (`session_duration_hours`).
  - Projects without `toggl_project_id` are counted as unmapped, never posted.
  - **Dry-run prints the exact outgoing payload** before any network call
    (solo-first guardrail), and posts nothing.
  - Idempotency: each entry is tagged `gittan` + `gittan:{project_id}:{day}`;
    re-runs skip candidates whose marker tag already exists in the window.
  - `--require-confirm` (default on) gates each post.
  - POST uses Toggl v9 with Basic auth; `start` carries a tz offset.
  - Doctor reports both token and workspace-id readiness for posting.
  - No network calls in tests (POST/LIST mocked); full autotest suite green;
    no Python file exceeds 500 lines.
- validation:

  | Scenario | Evidence |
  |---|---|
  | Per project+day aggregation | unit test on `build_toggl_entry_candidates` |
  | Unmapped project surfaced | unit test, project lacking `toggl_project_id` |
  | Dedup skip | unit test: marker tag present → skipped |
  | Dry-run prints payload, posts nothing | CLI test asserts payload echoed + no POST |
  | Confirm gate | CLI test: declined confirm → skipped, no POST |
  | Successful post body | unit test asserts POST fields + marker tag |
  | Doctor readiness | `tests/test_doctor_source_rows.py` extension |

- dependencies: D1, D2, D3 above; reference architecture `gittan jira-sync`
  (`collectors/jira.py`, `core/jira_sync.py`, `core/cli_jira_sync.py`).

---

### Unified credential onboarding in `gittan setup` (Jira + Toggl)

- priority: **now** (built alongside the push MVP)
- problem: secrets are env-var only, but only **GitHub** has a setup helper that
  persists them ([`core/setup_github_env.py`](../../core/setup_github_env.py)).
  Jira and Toggl rely on the user hand-editing their shell profile, and there is
  no single standard for where keys live.
- user value: one `gittan setup` flow prompts for Jira + Toggl keys and persists
  them the same way GitHub already does — consistent, discoverable, no new secret
  store to secure.
- decision: **model A — shell profile** (extend the existing pattern). Rejected
  for now: a `~/.gittan/credentials` file (new plaintext format to protect) and
  OS keychain (cross-platform + dependency cost). Env vars always take precedence.
- non-goals: OS keychain; a `~/.gittan` secret file; encrypting the shell profile.
- behavior:

```gherkin
Scenario: Setup persists Toggl credentials to the shell profile
  Given TOGGL_API_TOKEN and TOGGL_WORKSPACE_ID are unset
  When the user runs "gittan setup" and opts in to Toggl
  And enters an API token and workspace id
  Then both are written as export lines to the shell profile
  And a plaintext-storage note is shown for the secret
  And the next step points to "gittan doctor --toggl-source auto"

Scenario: Already-set credentials are left untouched
  Given JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN are all set
  When the user runs "gittan setup"
  Then the Jira step reports PASS and changes nothing

Scenario: Non-interactive run does not prompt for secrets
  When the user runs "gittan setup --yes"
  Then Jira/Toggl steps are skipped with a manual-setup hint
```

- acceptance:
  - `gittan setup` includes Jira and Toggl credential steps after GitHub.
  - Shared shell-profile primitives extracted to `core/setup_shell_profile.py`;
    `setup_github_env.py` reuses them (no behavior change, GitHub tests green).
  - Existing env vars are never overwritten; `--yes` mode never prompts for
    secrets.
  - Secret persistence shows a plaintext-storage warning.
  - No Python file exceeds 500 lines; full suite green.
- validation: `tests/test_setup_integration_env.py` (already-set PASS, declined
  skip, dry-run writes both fields + warning, partial input → ACTION_REQUIRED);
  `tests/test_setup_github_env.py` regression green.
- dependencies: none; uses the GitHub bootstrap as the reference pattern.

### Onboarding: verify-before-save + masked confirmation

- priority: **built** (task/onboarding-verify) — masked secret confirmation +
  live API verification (`verify_jira_credentials` /myself,
  `verify_toggl_credentials` /me) before any shell-profile write; failed
  verification persists nothing.
- problem: `gittan setup` credential entry hides the secret (questionary
  password) and writes it straight to the shell profile with no verification.
  This session proved the failure modes: a 236-char value pasted into
  JIRA_EMAIL, an empty token, and a wrong email-for-token — none caught until a
  manual `curl` round. A typo silently persists a broken credential.
- user value: you can't onboard a wrong/expired credential; mistakes are caught
  at entry, not on first failed sync.
- decision: do **not** echo secrets in cleartext by default. Instead:
  (1) after secret entry, show a **masked confirmation** (`ATATT…xz39, 192 chars
  — correct? [y/N]`); (2) **verify the credential live before persisting** —
  Jira `GET /rest/api/3/myself`, Toggl `GET /api/v9/me` — and only write the
  shell profile on success; on failure, report it and re-prompt/skip without
  writing. Mirrors the solo-first "dry-run shows exactly what will happen" rule.
- non-goals: cleartext secret echo by default; storing secrets anywhere but the
  shell profile (that decision stands — `[[invoice-text-ai-not-config]]` is a
  different concern).
- behavior:

```gherkin
Scenario: Wrong credential is rejected before writing
  Given the user enters a Toggl token that the API rejects
  When onboarding verifies it against /api/v9/me
  Then nothing is written to the shell profile
  And the user is told the credential failed and re-prompted

Scenario: Masked confirmation catches a paste error
  When the user pastes a value into a secret field
  Then a masked preview (prefix…suffix + length) is shown for confirmation
  And only a confirmed value proceeds to verification
```

- acceptance: secret entry is followed by a masked confirm; credentials are
  verified against the provider API before any shell-profile write; verification
  failure writes nothing and surfaces a clear reason; covered by tests (API
  mocked: 200 → write, 401 → no write).
- dependencies: `now` unified onboarding; reuses the Jira/Toggl auth clients.

### AI-generated invoice-friendly description (separate paid service)

- priority: **later** (own track / likely a paid add-on)
- problem: the time-entry description is currently `"{project_name} ({day})"`,
  fine for sync but not customer-facing. Billable text must describe *what was
  actually done that day* — so it has to vary per period, not be a fixed string.
- user value: Toggl entries (and downstream invoices) read like real billable
  line items without manual writing.
- **decision (maintainer, 2026-06-24):** do **not** source this from static
  config fields (`invoice_title` / `invoice_description`) — a constant string is
  the wrong model because the work differs each day. Instead, generate the text
  per project+day from the actual activity, the same way the personal
  `/gittan-invoice` skill produces customer text. This belongs in a **separate
  AI service that may be metered/paid**, kept personal/local, not in the free
  sync MVP.
- non-goals: hard-coding descriptions in config; bundling the AI generator into
  `toggl-sync`'s core path (the generator is a pluggable, opt-in producer).
- behavior:

```gherkin
Scenario: Opt-in AI description producer
  Given the user has enabled the (paid) description generator
  When toggl-sync builds an entry for a project+day
  Then the description is generated from that day's activity summary
  And without the generator enabled the description stays "{project_name} (day)"
```

- acceptance: `toggl-sync` exposes a pluggable description producer; default
  stays the current simple string; the AI/skill producer is opt-in and isolated
  so the free path needs no network/LLM. Privacy: send summaries, not raw traces
  (`source-evidence-policy.md`).
- dependencies: `now` Toggl push MVP; alignment with `/gittan-invoice` and the
  personal-skill/monetization direction.

### Local operation log + regret recovery

- priority: **next**
- problem: the solo-first model requires a local, append-only record of every
  push (operation ID, timestamp, target identifiers, payload hash) and a way to
  undo a regretted push.
- user value: "I regret this push" → identify the exact Toggl entries from a
  local log and delete them, or get clear manual-undo guidance.
- non-goals: bi-directional sync; undo of non-Gittan entries.
- behavior:

```gherkin
Scenario: Push is recorded locally
  When a Toggl time entry is posted
  Then a local op-log row records op id, timestamp, workspace+entry id, payload hash

Scenario: Rollback a regretted push
  Given a prior push is in the op-log
  When the user runs "gittan toggl-sync --rollback <op-id>"
  Then the matching Toggl entries are deleted via the API
  And the op-log marks them rolled back
```

- acceptance: op-log persisted under `$GITTAN_HOME`; `--rollback <op-id>` deletes
  the entries it created (Toggl `DELETE /time_entries/{id}`); idempotent rollback;
  manual-recovery guidance printed when an entry no longer exists.
- validation: unit tests for log write + rollback (DELETE mocked); re-run
  rollback is a no-op.
- dependencies: `now` item shipped; D4.

---

### Per-session granularity (opt-in)

- priority: **later**
- problem: project+day loses intra-day session detail some users may want in
  Toggl.
- non-goals: changing the default (project+day stays default).
- acceptance: `--granularity session|day` flag; dedup key extends to start time;
  default unchanged.
- dependencies: `now` item; revisit dedup key shape.

### Multi-workspace fan-out

- priority: **later**
- problem: a project may map to a Toggl project in a non-default workspace.
- acceptance: per-profile workspace override; doctor shows each workspace.
- dependencies: `now` item.

### Post via `reported_time` bridge

- priority: **later**
- problem: long-term, Calendar-confirmed time should drive posting, not the raw
  report payload (bridge fase 4).
- non-goals: building the bridge here (own spec/story).
- acceptance: `toggl-sync` can read candidates from `reported_time` records once
  they exist, without reworking the post client.
- dependencies: [`scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md)
  fases 1–3.

### Read time *from* Toggl (bi-directional)

- priority: **do not build yet**
- problem: the placeholder collector implies a pull direction.
- why not: the solo-first model explicitly excludes full bi-directional sync and
  broad inbound surfaces early. Keep Gittan the source of truth; push only.

### Auto-create Toggl projects

- priority: **do not build yet**
- why not: creating remote projects from local config is a side effect that
  conflicts with draft-first/minimal-write guardrails; surface unmapped projects
  instead and let the user create them in Toggl.

---

## Branch

`task/toggl-posting` from latest `origin/main`.

## Traceability

- story_id: GH-175 (tracked by PR #175)
- spec_status: draft
- implementation_status: in progress (`now` item)
- created_at: 2026-06-23
- last_updated_at: 2026-06-23
- implementation.pr: pending
- implementation.branch: task/toggl-posting
- implementation.commits: []
- validation.evidence: `tests/test_toggl_sync.py` (15 tests green); full suite run pending
- validation.decision: NO-GO (until `now` acceptance complete + suite green)
- related:
  - mirrors `gittan jira-sync` (`core/jira_sync.py`, `core/cli_jira_sync.py`)
  - product model: [`simple-invoicing-model.md`](../ideas/simple-invoicing-model.md)
  - future: [`scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md) fase 4
- changelog:
  - 2026-06-23: Initial draft (task-prompt form), shaped from the Jira/Toggl/Linear
    posting-state comparison.
  - 2026-06-23: Reformatted as a `gittan-product-owner` backlog; added solo-first
    guardrails (dry-run prints payload, op-log + regret recovery as `next`),
    ordered later/do-not-build items.
  - 2026-06-24: Added `now` item — unified credential onboarding in `gittan
    setup` for Jira + Toggl (model A, shell profile). Built: `setup_shell_profile.py`,
    `setup_integration_env.py`, wizard wiring, `tests/test_setup_integration_env.py`.
