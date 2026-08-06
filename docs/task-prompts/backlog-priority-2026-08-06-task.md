# Backlog priority pass — 2026-08-06 (product owner)

Planning pass after the open-PR queue was drained from **29 to 0** and the
scheduled Jules agents were retired (#512). No feature code in this pass:
priority, story-id hygiene, and one re-scope that a merge caused without anyone
noticing.

## Traceability

- story_id: `GH-513` (https://github.com/mbjorke/timelog-extract/issues/513)
- spec_status: approved
- implementation_status: n/a (planning artifact — no code)
- created_at: 2026-08-06
- last_updated_at: 2026-08-06
- implementation.pr: pending
- implementation.branch: `claude/many-open-prs-y8lun4`
- implementation.commits: []
- validation.evidence: this document (planning pass; labels applied, stragglers closed)
- validation.decision: GO
- changelog:
  - 2026-08-06: Initial pass. Successor to `backlog-priority-2026-07-26-task.md`
    (GH-472); lineage 2026-07-08 → 07-10 → 07-21 → 07-25 → 07-26 → 08-06.
    Closed #473 and #454 as shipped. Promoted #431 to `priority:now`, demoted
    #416 to `priority:next`. Re-scoped #408.

Labels remain the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`). Project 3 is the human view;
board writes need the `project` gh scope, which a hosted session does not have,
so this pass is complete once the labels are right.

---

## Finding: the drain was not backlog progress

Thirteen PRs merged on 2026-08-06. **One** of them advanced a `priority:now`
issue.

| | Count |
| --- | --- |
| PRs merged | 13 |
| Advanced a `priority:now` issue | **1** (#497 → #473) |
| Advanced a `priority:next` issue | 1 (#488 → #454) |
| Not in the backlog at all | **11** |

Meanwhile #408, #414, #416 and #448 — all `priority:now` — went untouched from
21–26 July through the entire episode.

This is not primarily an agent failure. The agents optimised what they could
*see*: the code in front of them. The backlog lived in issues and task-prompts
they never read. Their prompts said "check the open PR queue first"; nothing
said "check what is prioritised". A reviewer bot has the same blind spot by
construction — CodeRabbit and Greptile review a diff, and a diff cannot be
un-prioritised.

**Consequence for planning.** The bottleneck was never writing code. All 29 PRs
passed through review capacity, not build capacity. With the maintainer's time
reduced going forward, priority has to be ordered by **cost in maintainer
attention** — how much deciding and verifying an item demands — rather than by
size or age.

That principle produces one demotion and one promotion below, and they are the
only two judgement calls in this pass.

## Finding: shipped work outlived its own fix

Neither #497 nor #488 carried a `Closes #N`, so both issues sat open after the
work landed. This is the failure `docs/skills/gittan-product-owner.md` names
from #145/#146, repeating.

Closed in this pass:

| Issue | Shipped by | Note |
| --- | --- | --- |
| #473 git-commit hook `No module named 'core'` | #497 (`6b73b5e`) | "spool, don't import" — the default proposed in the 07-26 pass is what landed |
| #454 Impact 0.0 on decidable rows | #488 (`3fc8877`) | see the correction below |

**#454 is worth reading before touching neighbouring review work.** The first
attempt at it read `impact_hours == 0.0` as "no hour signal", but only
`build_url_candidates_from_gap_days` apportions unexplained hours per URL key.
`build_url_candidates` — the GitHub / Chrome / WordPress path — never sets the
field, and finalisation defaulted the absence to `0.0`. A filter written for
Lovable rows therefore parked *every* candidate from the other builder before
its human title was considered. `impact_hours` is now `Optional[float]`: a
missing measurement is not a zero measurement.

## Finding: #408 lost two thirds of its scope, silently

`#497` shipped two of #408's three scenarios. Nobody re-read the issue
afterwards, so it still reads as a three-scenario `now` item.

| Scenario in #408 | State after #497 |
| --- | --- |
| A commit is recorded as a structured event | **shipped** — hook spools, `capture_events()` drains into the ledger |
| Ledger write failure is not silent | **shipped** — `capture-errors.jsonl`, and the markdown write still happens |
| Markdown worklog becomes a view | **open** — the hook still writes markdown directly |

What remains is the least urgent of the three: markdown is currently written
*and* the ledger is populated, so no evidence is lost while this waits. Moved
to `next` with the scope corrected.

---

# Ordered backlog

## now

### 1. GH-431 — client names in committed docs

- priority: **now** (promoted from `next`, where it had sat since 2026-07-22)
- problem: roughly two dozen real client names are committed in public
  documentation. This repository publishes to PyPI and GitHub Pages, so the
  leak is live, not theoretical.
- user value: the product's first promise is local-first and trustworthy with
  business data. A public repo that leaks its own author's client list
  contradicts that promise more directly than any feature can support it.
- non-goals: rewriting git history (the names are already published — removal
  stops future exposure, it does not undo past); auditing `private/`, which is
  gitignored by design; changing the placeholder convention itself, which is
  already documented in `AGENTS.md` → *Test and fixture data hygiene*.
- behavior:

```gherkin
Scenario: A committed doc carries no live client identifier
  Given a documentation file tracked in the repository
  When it is scanned for identifiers from the maintainer's live configuration
  Then no project name, customer name, or tracked URL from that configuration appears
  And any example uses a neutral placeholder such as project-alpha or customer-a.test
```

- acceptance: every occurrence replaced with a neutral placeholder; the meaning
  of each example survives the substitution (a renamed example that no longer
  demonstrates anything is not a fix); a check exists that would fail on
  reintroduction.
- validation: the check runs in CI and fails on a deliberately reintroduced
  name. **The check must read its list of forbidden strings from local
  configuration at runtime and never commit that list** — a committed
  denylist of client names is the same leak with extra steps.
- dependencies: none.
- **NEEDS_HUMAN** — deciding what each anonymised example should say requires
  knowing what it was meant to demonstrate. An agent can find the occurrences;
  it should not invent the replacements unaided.

### 2. GH-414 — Chrome dashboard-work evaporation

- priority: **now** (unchanged)
- problem: per-URL-per-day thinning drops work that happened, so reported hours
  are lower than worked hours.
- user value: the core promise is hours you can invoice. Hours that evaporate
  are the most expensive kind of wrong — they cost money silently, and the
  operator has no signal that anything is missing.
- non-goals: review-queue presentation (#454, now closed); Lovable ambient
  mtimes (#448) — related symptom, different mechanism.
- acceptance: a fixture reproducing the thinning shows the events surviving into
  the report; existing thinning behaviour that is *correct* stays.
- validation: fixture test, no live config, no manual walkthrough.
- **Why first among the accuracy bugs:** verification is entirely automatic.
  Under a reduced time budget this is the cheapest correctness win available.

### 3. GH-448 — Lovable Desktop: open-app cache ≠ authorship

- priority: **now** (unchanged)
- problem: ambient cache/storage mtimes from an open app produce ghost projects
  and hours nobody worked.
- user value: the mirror of #414 — hours invented rather than lost. Both break
  the same promise.
- non-goals: the attendance taxonomy itself (#327), which is the general model;
  this is the specific collector behaviour.
- acceptance: a fixture with app-open-but-idle mtimes produces no authorship
  events; a fixture with real edits still does.
- validation: fixture test.
- dependencies: shares vocabulary with #327; does not require it.

## next

### GH-408 — markdown worklog becomes a view over the ledger

- priority: **next** (re-scoped; was `now` with three scenarios)
- Only the third scenario remains. Nothing is lost while it waits: the hook
  writes markdown *and* the ledger receives the event, so this is a
  consolidation, not a gap.
- dependencies: the spool and drain shipped in #497.

### GH-416 — beta onboarding dry-run, first external tester

- priority: **next** (demoted from `now`)
- The value is not in question — this is the only item that tells us whether
  the product works for someone who did not build it. The demotion is purely
  about cost: it consumes scheduling, a walkthrough, and interpretation of
  another person's confusion, all of which land on the maintainer and none of
  which can be delegated to an agent or a fixture.
- **Promote back to `now` the moment there is a week with maintainer time in
  it.** This is a parked item, not a deprioritised one — the distinction
  matters, and a reader six weeks from now will not infer it.

### Unchanged `next`

#454's closure does not move #414, #419, #448 or #327. #267 (work-unit v2),
#254 (shadow log slice 1) and #264 (setup write safety) keep their band.

## later / do not build yet

No band moves this pass.

**#326** ("Rename kanin-loop → review loop (multi-reviewer: CodeRabbit + Qodo)")
should be re-read rather than actioned: Qodo does not run on this repository,
which #512 corrected in the contributor docs. The issue's premise is stale even
though its underlying point — the loop has more than one reviewer — is not.

## Non-goals for this pass

- Implementing any of the above.
- Board (Project 3) writes — hosted sessions cannot; labels are the source of
  truth and are now correct.
- Deleting merged/closed `task/*` branches; ~30 remain on origin, deliberately
  untouched.
- Re-litigating the retired agents. `#512` is the record.

## Decisions for the maintainer

1. **#431 replacements** — an agent can locate every occurrence, but what each
   anonymised example should *say* needs someone who knows what it was
   demonstrating. Expect to review that diff properly rather than skim it.
2. **The #431 CI check must not commit the denylist.** Proposal: read the
   forbidden strings from the local `timelog_projects.json` at runtime and skip
   the check when that file is absent, so CI on a fork degrades to a no-op
   rather than to a leak. Confirm before an agent implements it.
3. **#416 re-promotion trigger** — name the condition now ("the first week I
   have two free evenings") so it is not left to drift indefinitely.
4. **Performance work** — four optimisations were closed unmerged (#479, #482,
   #485, #492) with their findings preserved in `.jules/bolt.md`. The open
   question raised in that discussion stands: a broad profile of one *real*
   report would say whether any of them touched a real bottleneck. Not
   scheduled here; it is a one-session task whenever it is wanted.
