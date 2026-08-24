# What 0.5 still owes, and what it never did

A scope pass over the 38 open items on the **Gittan 0.5** board, run when the
release branch was already cut. The question was not "what could we build" but
"what does 0.5 still owe a user, and what is only on this board because it was
once mentioned".

No code in this pass.

## Traceability

- story_id: `GH-576`
- spec_status: approved
- implementation_status: not built
- promote: no
- created_at: 2026-08-23
- last_updated_at: 2026-08-24
- implementation.pr: pending
- implementation.branch: `task/gittan-0-5-scope-triage`
- implementation.commits: []
- validation.evidence:
  - board read via `gh project item-list 3` (314 items: 276 Done, 38 open)
  - three "open" items cross-checked against the code rather than their status
  - `git_repo` coverage measured against a live profiles config (counts
    deliberately not quoted here — see #515)
- validation.decision: GO
- changelog:
  - 2026-08-23: Initial pass, cut while `release/0.5.0` was open.
  - 2026-08-24: Greptile review — `promote: no`; #262 is five
    `core.repo_slug` importers, not twelve; #408 is partial (keep open for
    worklog-as-view, list on 0.6); #524 must surface the dark `git_repo`
    gap in both the report and `--source-summary`. Canonical
    `implementation_status: not built` (planning artifact; no code in this
    pass).

Labels remain the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`). This spec proposes label and
board changes; it does not open issues.

---

## What the board says, and where it is wrong

276 of 314 items are Done — 88%. That number understates, because the board
lags the code. Three items were checked against the repository instead of their
status field:

| Item | Board says | The code says |
| --- | --- | --- |
| #262 worktree-invariant attribution via repo slug | Backlog | `core/repo_slug.py` exists and **five collectors import it directly**. Built. |
| #408 commit events land in the shadow log | Ready | The ledger holds `git-commit` records in bulk. **Partial** — worklog-as-view (render Markdown from the ledger) is unbuilt. Keep open. |
| #524 `git_repo` unset leaves commit evidence dark | Backlog | **No profile** sets `git_repo`. Still true, and it bit us. |

#262 should be verified and closed rather than carried into another release.
#408 is only partial: storing `git-commit` records completes the ledger write,
not the remaining worklog-as-view scenario, so it stays open and moves to 0.6.
The third is the opposite: an issue that predicted a failure, was not
built, and then produced exactly the failure it predicted.

## The shape of what is left

Of the 38 open items, **17 are 44 days old or more** and eight are `later` from
the same July planning pass. Age is not by itself an argument for dropping
something, but a `later` item that has survived two releases untouched is
telling you where its real priority is.

Two items, **#533 and #534**, are the same request written twice.

---

## now — keep in 0.5

Four items, each of which 0.5 itself demonstrated the need for.

### #515 — Prevent client data reaching issues, PR bodies and comments

`priority:now`, open 17 days. During this release an agent published the
maintainer's measured ledger counts into a code comment, a test docstring, a
commit message and a PR body. A reviewer caught it; nothing in the repo did.
The guard exists for docs (`scripts/check_docs_no_client_data.py`) and does not
cover the surfaces where it actually happened.

```gherkin
Feature: Operational data does not leave the machine through review surfaces

  Scenario: A commit message carries a measured count from the operator's data
    Given a commit message contains a figure derived from the local ledger
    When the pre-push guard runs
    Then the push is refused, naming the line and the figure

  Scenario: A PR body carries a measured count from the operator's data
    Given a PR body contains a figure derived from the local ledger
    When the CI or API-triggered check runs
    Then the check blocks publication or merge, naming the line and the figure
```

**Acceptance:** the pre-push guard rejects commit messages carrying figures
traceable to local data, naming the offending text; a separate CI or
API-triggered check blocks PR publication or merge when PR bodies contain such
figures.

### #524 — `git_repo` unset leaves commit evidence silently dark

`priority:next` today; **promote to `now`**. Measured on a live config: no
profile sets `git_repo`, so the `Git commits` collector reports
`No profile has git_repo configured` and contributes nothing. The word that
matters is *silently* — the report is complete and quiet about what it could not
see.

```gherkin
Feature: A dark source says so where the operator will look

  Scenario: No profile configures a git repository
    Given no profile in the config sets git_repo
    When the operator runs a report
    Then the report surfaces that commit evidence is unavailable
    And `--source-summary` also surfaces that gap
    And both name the one change that would enable it
```

**Acceptance:** a run with zero `git_repo` profiles surfaces the gap in both the
report and `--source-summary`; the message says what to set.

### #533 / #534 — auto-tag the release when the version bumps on main

No priority label, open 15 days, and **duplicated**. This release ended with a
hand-typed `git tag`, which is the step most likely to be forgotten and the
reason a version can exist in `pyproject.toml` and nowhere else.

**Acceptance:** merging a version bump to `main` produces the tag; the existing
`.github/workflows/pypi.yml` workflow takes it from there. Close one of the two as a duplicate.

### #550 / #562 — hook follow-ups

`priority:now` and `later` respectively, both touching the code this release
changed twice. Cheap to finish while the context is warm; expensive to
rediscover later.

---

## next — 0.6, and they are the real 0.6

Accuracy work. None of it blocks a release, all of it makes hours truer, and it
is the coherent theme for the following version:

- #327 attendance taxonomy: presence ≠ authorship
- #332 presence brackets evidenced sessions
- #367 / #368 / #369 session-label provenance, window, tab ownership
- #414 Chrome dashboard-work evaporation (currently the only *In progress* item)
- #523 webmail title churn inflating events
- #531 golden-home coverage: 2 of ~24 collectors verified
- #540 intent provenance recorded but never enforced

**#416, the beta onboarding dry-run, is the exception.** It is listed as
accuracy-adjacent but it is really the exit criterion: the first external tester
end to end. Everything in 0.5 was measured on one machine, whose configuration
is nine months of accumulated exceptions. Until someone else runs it, the
zero-config claim is a claim.

**#408 stays open on 0.6** for the remaining worklog-as-view scenario: Gittan
still cannot generate or append the Markdown worklog from the ledger. Storing
`git-commit` records in bulk is done; that is not enough to close the issue.

## later — off the 0.5 board

Real work, no evidence it belongs to this release:

- #222 `gittan map` merge UX, #237 formalize auto-commit as a setup command,
  #251 Screen Time warning recalibration, #264 setup config write safety
- #248 Claude Desktop cached events, #255 Lovable Desktop cache-mtime
- #239 command-surface doc, #252 feature inventory generator, #241 landing
  rewrite, #329 module renames
- #263 reported/approved time layer, #410 presence blocks + anchor attribution
- kanin-loop tooling: #276, #320, #272, #326

## do not build yet

- **#266** brainstorm handout — already labelled `do-not-build`, 53 days old.
  Close it. A brainstorm that has not happened in two months is not backlog.
- **#242 GitHub Marketplace app** — the strategic bet, and the one item here
  that should not be decided by a triage pass.

## Close as built

- **#262**, after a verification run. It is carried as open work that the code
  already does, which is the drift
  `docs/decisions/backlog-priority-surfaces.md` warns about.
  Do not close **#408** from this pass — worklog-as-view remains unbuilt.

---

## What this pass deliberately did not do

It did not re-plan 0.5 around what shipped. Most of this release — attribution
without configuration, anchors in the payload, replaying today, the hook guard,
the silent failures — **was not on this board**. It came from following a
question about mobile hours until it hit ground.

That is worth naming rather than tidying away: the board tracked what was
planned, and the release was mostly made of what was found. A 0.6 board that
only lists the 38 leftovers will predict the next version about as well.
