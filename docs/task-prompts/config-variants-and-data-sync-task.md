# Config as tested, versioned, portable data

A product-owner pass on two asks that share one substrate: verifying Gittan
against configuration variants instead of one maintainer's live data, and making
the data directory portable so work started on one device is attributed on
another.

No code in this pass.

## Traceability

- story_id: `GH-531`
- substrate: `GH-237` (promoted by this pass; blocks the items below)
- spec_status: approved
- implementation_status: not built (planning artifact — no code)
- created_at: 2026-08-07
- last_updated_at: 2026-08-07
- implementation.pr: pending
- implementation.branch: `task/config-variants-and-data-sync`
- implementation.commits: []
- validation.evidence:
  - inspection of the golden-home fixture harness and the collector registry
  - inspection of a live data directory against
    `docs/runbooks/gittan-data-autocommit.md` (findings below; the directory
    itself stays local, it holds customer and invoice data)
- validation.decision: GO
- changelog:
  - 2026-08-08: Review pass. Split the combined `story_id`, corrected backup
    retirement from `next` to `later` (it is two dependencies deep and has no
    issue, which is the correct state for `later`), and recorded #535 as
    blocking #237 — found by installing the timer for real after this was
    drafted.
  - 2026-08-07: Initial pass.

Labels are the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`).

---

## Why this is one pass and not two

Verifying config variants and syncing a data directory look unrelated. They are
the same question asked twice: **is configuration data we can hold, move, and
reason about, or is it a state that happens to exist on one machine?**

Today it is the second. That single fact produces both symptoms: tests lean on
whichever config the maintainer happens to have, and configuration cannot travel
between devices. Make config a versioned artifact and both get easier at once —
a variant becomes something you can check out, and a device becomes something
you can sync.

## What is actually true today

Three findings, each verifiable in the repo.

**The synthetic-data harness exists and covers almost nothing.**
`tests/golden_home_fixtures.py` materializes fabricated source data into a
throwaway `HOME`, so the full report path can run with no real local data and no
network. It is the right design and it is already wired into
`scripts/run_golden_eval.py`. It has **two** materializers, `chrome_history` and
`cursor_composer_headers`, against a registry of roughly two dozen collectors.
Everything else is exercised either by narrow unit fixtures or by whatever the
maintainer's machine contains. That is the whole of the "too reliant on my data"
problem, and the fix is coverage in an existing harness rather than a new idea.

**Config variants already exist, as folklore.** Alternate profile directories
get hand-built for demos and recordings. They work, they are not versioned, not
described anywhere, and not reachable from a test. Every one of them is a
configuration variant somebody needed and then lost.

**The data directory's safety mechanism is installed by hand and stops
silently.** `docs/runbooks/gittan-data-autocommit.md` came out of incident
`2026-07-01-observed-cache-overwrite-degrades-closed-months.md`: the observed
cache was untracked, so a bad write destroyed closed-month data with no history.
The runbook's answer is a git repo plus a timer the user installs by editing a
launchd plist. In practice the repo gets initialised, the timer does not survive,
commits stop, and nothing anywhere reports it. Meanwhile the code still writes
timestamped backup copies beside the config, because git was never trusted to be
the mechanism, so the directory accumulates copies under several different
naming schemes.

That last one is the third instance today of the same failure: a mechanism that
looks installed, is dead, and is invisible because the thing it guards keeps
working until the day it doesn't. See #366, and the collector measurement in
#529's thread.

---

## Backlog

### #237 — `gittan setup-data-autocommit`, promoted

- priority: **next** (from `later`), behind #535 — the global commit hook fires
  on the data directory itself, so shipping this command first would hand every
  user an infinite commit loop. Found while installing the timer manually after
  this spec was drafted.
- problem: the protection that came out of a real data-loss incident depends on
  a user hand-editing a launchd plist, and there is no check that it still runs.
  A runbook step that must be performed once, correctly, by hand, and then keeps
  working invisibly for months is not a safety mechanism.
- user value: the incident cannot recur silently.
- non-goals: pushing anywhere by default. Commit-only stays the default; the
  directory holds customer and invoice data, so a remote is opt-in and must be
  private.
- behavior: a command installs the timer with explicit consent, and `doctor`
  reports whether it is actually committing.

```gherkin
Feature: The data directory protects itself without hand-editing a plist

  Scenario: Installing with consent
    Given the data directory is not yet under version control
    When the operator runs the setup command
    Then the risk and what gets committed are stated before anything is written
    And the repository and the timer are installed only after explicit consent
    And pushing to a remote is not enabled

  Scenario: A stopped timer is visible
    Given the timer was installed previously
    And no commit has been made for longer than the expected interval
    When the operator runs `gittan doctor`
    Then the row reports the protection as stalled, with the last commit time
    And it is distinct from "not installed"

  Scenario: Opting in to a remote
    Given the operator asks to push
    When the remote is configured
    Then the command refuses a public remote
    And states that the directory holds customer and invoice data
```

- acceptance: install, stall detection, and the public-remote refusal each work
  on a clean profile. Doctor distinguishes "not installed", "installed and
  committing", and "installed but stalled" — the middle state is the one that
  does not exist today.
- validation: install against a temporary `GITTAN_HOME`, make a change, confirm
  a commit; freeze the clock past the interval and confirm doctor reports
  stalled. Never against the operator's live data directory.
- dependencies: none. It is the substrate for everything below.

### Retire the timestamped backup copies once git is the mechanism

- priority: **later** — it sits behind #237, which sits behind #535, so calling
  it `next` would claim a position nothing can be picked up from. No issue is
  filed for it yet, which is the correct state for a `later` item.
- problem: the config directory accumulates copies under several different
  naming schemes, written by different code paths at different times. They exist
  because there was no history. Once the directory is a git repo with a working
  timer there is history, and the copies are noise that makes the directory hard
  to reason about — including for the operator trying to find the current file.
- non-goals: deleting anything a user already has. This is about what Gittan
  writes from now on.
- acceptance: a mutating command commits instead of copying, or copies only when
  the directory is not a repo. Existing copies are left alone, and one command
  can list them so the operator can prune deliberately.
- dependencies: #237. Do not remove the belt before the braces are proven.

### Golden-home materializer coverage for the collectors that carry hours

- priority: **next**
- problem: two materializers against roughly two dozen collectors means most of
  the report path has never run against data anyone designed. Bugs are found by
  the maintainer noticing something wrong in his own report, which is exactly the
  loop that has to stop.
- user value: a change to a collector can be shown to be right before it reaches
  anyone's real data.
- non-goals: covering every source. Order by how many hours a source attributes
  and how much damage it does when wrong.
- behavior: each materializer writes one collector's real on-disk shape — the
  SQLite schema, the JSONL layout, the log format — into a throwaway `HOME`, so
  a golden dataset can assert end-to-end hours.

```gherkin
Feature: A collector can be verified without anyone's real data

  Scenario: A collector runs against fabricated on-disk data
    Given a golden dataset declares home fixtures for a collector
    When the golden eval runs
    Then the collector reads only the throwaway HOME
    And no path outside it is opened
    And the resulting hours match the dataset's expectation

  Scenario: A collector with no materializer is visible as uncovered
    Given a collector in the registry has no home-fixture materializer
    When coverage is reported
    Then that collector is listed as unverified against synthetic data
```

- acceptance: the uncovered list exists and shrinks. First materializers are the
  ones that attribute the most hours today, which the collector registry and a
  source-summary run can name — not a guess.
- validation: run the golden eval with the real `HOME` pointed somewhere empty
  and confirm results are unchanged, which proves the fixtures are actually
  self-contained.
- dependencies: none, but the variant corpus below is much cheaper after it.

### A committed corpus of configuration variants

- priority: **later**
- problem: the shapes that break Gittan are configuration shapes — many
  profiles, none, duplicate slugs, a profile with no `git_repo`, remote-only
  repositories, overlapping `match_terms`, a worklog path that does not exist.
  Each is currently discovered when a real person hits it.
- behavior: a small set of committed synthetic configs, each named for the shape
  it represents, that any test or golden dataset can point at. The hand-built
  demo profiles are the informal version of this and should be folded in rather
  than kept in parallel.
- acceptance: a test can request a variant by name; adding a variant does not
  require touching a test; the variants contain no real customer, project, or
  path data.
- dependencies: the materializer work above, so a variant can be exercised
  end-to-end rather than only unit-tested.

### Data directory portable across devices

- priority: **later**
- problem: work started on one device should be attributed when the operator
  returns to another. Today the data directory is per-machine, so config written
  on one is invisible on the other.
- non-goals: a Gittan-hosted sync service. The product's claim is local-first,
  and the directory holds customer and invoice data; a service would trade the
  differentiator for convenience.
- behavior: the same git repository from #237, with an opt-in **private** remote,
  is the sync mechanism. Pull on start, commit on change, push on the timer.
- open questions, which is why this is `later` and not `next`:
  - Merge conflicts on config are a real editing problem, not a git problem. Two
    devices editing profiles need a resolution the operator can understand
    without reading a diff.
  - The observed cache has keep-max semantics; two devices with divergent caches
    need a defined merge, or the guarantee that a re-run never degrades a closed
    day is lost across devices.
  - What a mobile device actually writes is unspecified. Establish that before
    designing sync for it, or the design will be for an imagined client.
- dependencies: #237, and a decision on each question above.

---

## Ordering

Nothing here enters `now`. That set is already deep and the binding constraint is
maintainer attention, so this pass adds to `next` and `later` only.

Within the pass: **#535 first**, because it was found after this spec was drafted
and #237 cannot ship over it — the global hook fires on the data directory, so an
auto-commit timer would churn forever. Then #237, the substrate, which closes a
known incident path. Then materializer coverage, the direct answer to
verification depending on one machine. Backup retirement waits for #237 to be
proven, and the variant corpus and device portability get much cheaper once the
first items exist.

## Open decisions

1. **Which collectors get materializers first?** Answer from a source-summary
   run over a real window — how many hours each source attributes — rather than
   from intuition. That measurement does not exist yet and is the first task.
2. **Do variants live in the repo or in a separate fixture repository?** In-repo
   is simpler and reviewable; separate keeps the main repo small and lets a
   variant carry a full directory tree. Decide before the corpus is built, not
   after.
3. **Does `doctor` warn about a stalled timer by default?** It is a real risk,
   and it is also a warning a user who deliberately declined the timer should not
   see forever.

## Non-goals for this pass

No code. No hosted sync. No changes to what the collectors currently read.
