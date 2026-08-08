# Attribution without configuration — setup stops being a gate

A product-owner pass triggered by a first-run session on a clean machine. It
places five defect reports (#521–#525) in the backlog and promotes one direction
that several existing specs already point at without anyone sequencing them.

No code in this pass.

## Traceability

- story_id: `GH-526` · slice 1 = `GH-527`
- spec_status: approved
- implementation_status: not built (planning artifact — no code)
- created_at: 2026-08-07
- last_updated_at: 2026-08-07
- implementation.pr: pending
- implementation.branch: `task/zero-config-project-attribution`
- implementation.commits: []
- validation.evidence:
  - first-run session on a clean machine, 0.4.0 (raw transcript stays local; it
    carries third-party client data and must not be quoted in the repo)
  - defects filed and verified in code: #521, #522, #523, #524, #525, #529
  - priority labels applied per the ordering below
- validation.decision: GO
- changelog:
  - 2026-08-07: Second review pass. Restated the setup-friction consequence as a
    structural one and dropped the last observational metrics, so no argument
    here rests on one machine's configuration.
  - 2026-08-07: Review pass. Restricted slice 1 to git-remote anchors (the dir
    leaf is not a durable identity), defined the `--format json` row shape for
    derived projects, required an explicit temporary config path in the no-write
    validation covering both the present and absent file, and added the Ctrl-C
    cancellation case to #522.
  - 2026-08-07: Added #529 to `now` after tracing the unrecognised top anchor to
    the scraped-path fallback in two collectors. It gates #527.
  - 2026-08-07: Initial pass. Successor to `backlog-priority-2026-08-06-task.md`
    (GH-513).

Labels are the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`).

---

## The problem the first run exposed

Two complaints came out of the session, and they are the same complaint:

1. The project-mapping step in `gittan setup` defaults to **Yes**, and the
   operator wanted it to default to **No**. Project setup should not be a
   necessary step.
2. Wiring project → customer is too laborious to be worth doing up front, so it
   does not get done. The consequence is structural rather than anecdotal: a
   profile can exist and still leave the strongest evidence source unwired,
   because the wiring is a separate manual step nobody has a reason to finish
   (#524).

The underlying design fault is that **Gittan currently requires configuration
before it can attribute anything**. That conflates two different things:

| | What it is | Can it be derived? |
| --- | --- | --- |
| **Identity** | which repository / working directory this work belongs to | **Yes** — the git remote already says `owner/repo` |
| **Billing** | which customer, what invoice title, what rate | **No** — a human has to declare it |

Today setup asks for both at once, at the moment the user knows least and cares
least. Identity does not need a human, and billing does not need to happen before
the first report.

Split them, and setup stops being a gate: a report can attribute work to
`owner/repo` with an empty config, and configuration becomes the thing you do
**when you want to bill**, on the projects you actually bill.

## This direction is already specced, just not sequenced

Nothing here is a new invention. It is four existing items that nobody has put in
order:

| Issue | State | What it contributes |
| --- | --- | --- |
| #262 | **built** | worktree-invariant attribution from git remote / repo slug — the derivation already exists |
| #257 | in progress, `later` | new-repo mapping derives the slug read-only and asks only for customer + display name |
| #410 | not built, `later` | anchor attribution with `match_terms` demoted to fallback |
| #406 | not built, `next` | guardrail: anchor plans must **not** bulk-apply to config |

The derivation is done. The friction reduction is half-built and parked at
`later`. This pass sequences them behind one framing rather than adding a fifth
overlapping spec.

## The constraint that must not be broken

"Auto-detect new project config when you run a report" cannot mean "a report
writes to `timelog_projects.json`".

Issue #406 exists specifically to stop bulk anchor → config application, the report
postamble already warns *"do not bulk-apply them as `match_terms`"*, and the
setup and mapping heroes promise *"Every write is explicit and reviewable"* and
*"Nothing is saved without your approval"*. A report that silently edits config
would break the product's central claim, and it would do it in the file the
maintainer treats as critical local data.

**Resolution:** auto-detection produces **derived, in-memory attribution for this
report**, persisted nowhere. Config keeps its current meaning — a declaration a
human made — and gains no new writer. The user sees their work attributed
immediately; they opt in to persistence only when they want billing.

Non-negotiable: no pass in this spec writes `timelog_projects.json` without an
explicit user action.

---

## Backlog

### Setup's project-mapping prompt defaults to No

- priority: **now**
- problem: the mapping step defaults to Yes and reads as required. It is the
  longest, most tedious part of first run, it arrives before the user has seen a
  single report, and backing out of it is currently destructive (#522).
- user value: first run reaches a working report without a configuration detour.
- non-goals: removing the step, changing what it does when accepted, or changing
  any other prompt's default.
- behavior: the prompt still appears; its default answer flips to No, and the
  wording says mapping is optional and can be run later with `gittan map`.

```gherkin
Feature: Project mapping is offered, not imposed

  Scenario: The default answer is No
    Given a first run of `gittan setup`
    When the project mapping step is reached
    Then the highlighted default answer is No
    And the prompt states that mapping is optional
    And it names `gittan map` as the way to do it later

  Scenario: Declining mapping still completes setup
    Given the operator accepts the default
    When setup continues
    Then the remaining steps run
    And the summary reports mapping as skipped, not failed
    And the closing next-steps do not instruct the operator to re-run `gittan setup`
```

- acceptance: default is No; declining is a normal completion; the wizard's
  closing text no longer tells the operator to run `gittan setup` again to finish
  mapping (today it does, which walks them back into #522).
- validation: run `gittan setup` on a clean profile, accept every default, and
  confirm it completes with mapping skipped and a report still runnable.
- dependencies: none. Ship independently of everything below.

### #522 — cancelling one mapping prompt discards every completed mapping

- priority: **now**
- problem: verified at `core/mapping_review_flow.py:202`. Completed answers
  accumulate in a local list; both cancel branches return `None` and drop it.
  `questionary` also returns `None` on Ctrl-C, so an interrupt has the same
  effect.
- user value: the operators who *do* opt into mapping stop being punished for it.
- non-goals: the mapping semantics in #222 (which option is default, what merge
  does). Different fix, different code.
- acceptance: cancel means "stop asking", not "discard". Either apply what was
  completed and say so, or offer save-or-discard explicitly at the cancel point.
- validation: complete one mapping, then cancel at the next prompt, and confirm
  the first survived. Repeat with Ctrl-C at the next prompt rather than a menu
  cancel: `questionary` returns `None` for both, so the interrupt path has to be
  proved separately, not assumed.
- dependencies: none. Pairs naturally with the default-No flip: one makes the
  step optional, the other makes it safe.

### #529 — any `/Users` path in an IDE log line becomes a workspace

- priority: **now** — fixed, PR #530
- problem: `collectors/vscode_fork.py:290` and `collectors/cursor.py:237` fall back
  to scraping the first `/Users/...` substring out of a log line and treating it
  as the workspace. A path mentioned in a log line is not a workspace, and the
  only guards are denylists, so anything nobody thought to exclude passes. A
  directory some harness writes session data into can therefore reach the top of
  the anchor list, ahead of real repositories, because the count is of log lines
  mentioning a path rather than of work.
- user value: the first report stops leading with something the user cannot place.
- non-goals: the workspace-id path (step 1) is correct and stays.
- acceptance: a scraped path is used only when it independently looks like a
  workspace — present in `workspace_map`'s values, or resolving to a git remote.
  Otherwise the line produces no anchor. Both collectors fixed together.
- dependencies: gates #527. Derived attribution must not inherit these anchors,
  or zero-config reports will lead with junk instead of `Uncategorized`.
- note: event counts here measure log lines mentioning a path, not work, which is
  why the ranking is inverted. The ranking half is tracked on #222.

### Report-time attribution for unmapped repositories (slice 1)

- priority: **next**
- problem: work in a repository with no profile lands as `Uncategorized` or under
  an unrelated project, and the only remedy offered is a configuration session.
  The identity was available the whole time in the git remote.
- user value: a useful report on the first run, with no config at all.
- non-goals: writing config; inventing customers; branch- or session-title-derived
  identity (#406 keeps those out of apply paths); anything about billing.
- **scope limit — git remotes only.** A derived row is created only where a git
  remote yields `owner/repo`. Working-directory anchors are explicitly out of
  this slice: the dir leaf is not a durable identity, it collides across
  machines, and #529 showed how easily a junk leaf reaches the user. Local-only
  repositories and non-git directories keep today's behaviour until a safe
  local identity key is decided (open decision 3), which is its own slice.
- behavior: when events carry a repository anchor with no matching profile, the
  report attributes them to the derived slug and marks the row as derived, so it
  is visually distinct from a declared project.

```gherkin
Feature: A report attributes unmapped repositories without configuration

  Background:
    Given events carry a git remote of "owner/widgets"
    And timelog_projects.json has no profile matching it

  Scenario: Derived attribution replaces Uncategorized
    When the operator runs `gittan report`
    Then the hours appear under a row derived from the repo slug
    And the row is marked as derived rather than declared
    And timelog_projects.json is not modified

  Scenario: A declared profile always wins
    Given a profile does match "owner/widgets"
    When the operator runs `gittan report`
    Then the declared profile is used
    And no derived row is created for it

  Scenario: Derived rows are not billable
    Given a report contains derived rows
    When the operator reviews it
    Then derived rows carry no billable total
    And the report states that billing requires declaring the project

  Scenario: Ephemeral signals stay out
    Given events carry only a branch name or a session title
    When attribution runs
    Then no derived project row is created from them
```

- acceptance: a day of work in three git repositories produces three attributed
  rows; derived rows are structurally distinct from declared ones in both the
  terminal and JSON output; branch, session-title, and working-directory signals
  produce no rows.
- **`--format json` contract.** Consumers must not be able to mistake a derived
  project for a declared one, so the shape is part of the acceptance, not an
  implementation detail:

  | Field | Declared project | Derived project |
  | --- | --- | --- |
  | `project` | profile name | the derived `owner/repo` slug |
  | `derived` | `false` | `true` |
  | `customer` | as configured | `null` |
  | `billable_hours` | as computed | `null`, never `0.0` |

  `null` rather than `0.0`, so a consumer summing the field cannot silently
  treat a derived row as a zero-value billable one. Bumping
  `TRUTH_PAYLOAD_VERSION` is part of this slice.
- validation: point the run at an **explicit temporary config path**, never the
  ambient one — a report must not be able to resolve the operator's live
  `timelog_projects.json` during a no-write test. Cover both directions: an
  existing fixture file is byte-identical afterwards, **and** an absent config
  file is still absent afterwards, so the report cannot be creating one. Then
  assert the row shape above in `--format json`.
- dependencies: #262 (built) supplies the derivation. Must not violate #406.
  Overlaps #410 — fold rather than duplicate.

### #521 — `gittan status` can exit with no output and no error

- priority: **next**
- problem: `except Exception` cannot catch `BaseException`, and the Rich spinner
  clears the region on teardown, so the command can end mute.
- why not `now`: the specific occurrence is not reproducing and the exit code was
  not captured. Promoting an unreproduced defect spends the scarce resource on a
  hunt. The defensive fix (never exit mute) is worth doing on its own and does
  not need the root cause.
- acceptance: every exit path prints a summary, an explicit empty result, or an
  explicit error.

### #523 — webmail title churn inflates events and smears projects

- priority: **next**
- problem: one background tab produced roughly forty events in a day and put its
  project into nearly every session.
- dependencies: same source and the same root question as #414 (dashboard work
  evaporating). Solve them together or the weighting will be fixed twice in
  opposite directions.

### #524 — `git_repo` unset on every profile leaves commit evidence dark

- priority: **next**
- problem: the least ambiguous local evidence contributes nothing, and doctor
  reports it as a dot among dots.
- note: this becomes much less severe if report-time attribution lands, since the
  remote is then read directly. Sequence after it and re-scope, rather than
  building an auto-filler that the attribution work makes redundant.

### #525 — `gittan -v` rejected while the installer says `-V`

- priority: **later**
- small, but it fires at the exact moment a new user decides whether the tool
  works. Cheap to fold into any CLI-surface change.

### Billing as an opt-in layer over derived identity

- priority: **later** (no issue yet — promote when the slice above lands)
- once a report attributes work without config, declaring a project means
  attaching billing to an identity that already exists: pick a derived row, name
  the customer, done. That is the same shape #257 already specifies for
  `gittan map`, applied at the point the user has a reason to care.
- promote only after report-time attribution ships; specifying it earlier would
  guess at a UI whose input does not exist yet.

---

## Ordering

The existing `now` set stays ahead. #431 and #515 are trust failures and gate
inviting anyone external in; #414 and #448 are correctness bugs a new user hits
on day one.

1. #431 — client names in committed docs
2. #515 — client data reaching issues and PR bodies
3. #414 — Chrome dashboard-work evaporation
4. #448 — Lovable Desktop open-app ≠ authorship
5. **#529** — junk anchors leading the report; gates #527
6. **default-No flip** — hours of work, removes the friction the first run named
7. **#522** — stops the mapping step destroying work

Then `next`: report-time attribution slice 1, #521, #523 (with #414), #524
(after attribution), #416.

The two new `now` items are deliberately small. The capacity rule is that
maintainer attention is the binding constraint, so items that convert a first-run
objection into a fixed default, in one sitting, rank above items that are larger
but not yet forced.

## Open decisions

1. **How is a derived row displayed?** A prefix, a separate section, or a column
   flag. It must be unmistakable without making the report noisy.
2. **Does a derived row carry hours into totals?** Proposal: yes for observed
   totals, never for billable. Needs confirming against the accuracy guardrails
   before implementation.
3. **What is the identity key when there is no remote?** Settled for this slice
   by excluding it: derived rows require a git remote, so local-only
   repositories and non-git directories keep today's behaviour. Still open for
   the follow-up slice — a directory name collides across machines and projects,
   and a path hash is already ruled out — so nothing here should be built on the
   assumption that a local-only identity exists.
4. **Does the default-No flip apply to `gittan setup --yes`?** Non-interactive
   runs already skip prompts, so probably moot, but confirm before changing the
   default.

## Non-goals for this pass

No code, no collector changes, no release. The pass is complete when the labels
match the ordering above, the two new items have issues, and this spec is
committed.
