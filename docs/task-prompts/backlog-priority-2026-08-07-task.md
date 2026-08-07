# Backlog priority pass — 2026-08-07 (product owner)

A one-issue pass. It reverses a call made in `backlog-priority-2026-08-06-task.md`
(GH-513) one day earlier, because the reason that call was made has been replaced
by a better reading of the same constraint. No feature code.

## Traceability

- story_id: `GH-516` (https://github.com/mbjorke/timelog-extract/issues/516)
- spec_status: approved
- implementation_status: not built (planning artifact — no code)
- created_at: 2026-08-07
- last_updated_at: 2026-08-07
- implementation.pr: pending
- implementation.branch: `claude/gittan-omriktning-partner-02debf`
- implementation.commits: []
- validation.evidence:
  - label applied: #416 `priority:now` (reversing the 08-06 demotion)
  - #416 body re-scoped: 2–3 testers, demo raw material added as acceptance
  - comment on #513 recording why its demotion is reversed
- validation.decision: GO
- changelog:
  - 2026-08-07: Initial pass. Successor to `backlog-priority-2026-08-06-task.md`
    (GH-513); lineage 2026-07-08 → 07-10 → 07-21 → 07-25 → 07-26 → 08-06 → 08-07.

Labels remain the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`).

---

## The constraint, read correctly

GH-513 established that maintainer attention, not code throughput, is the scarce
resource, and ranked accordingly. That holds and gets more true: from September
onward there is materially less hands-on coding time, so this is a permanent
operating rule rather than one pass's tiebreaker.

GH-513 then applied it to #416 ("Beta onboarding dry-run: first external tester
end-to-end") and demoted it to `priority:next`, reasoning that scheduling and
walking a tester costs exactly that scarce resource.

That is the wrong conclusion from the right premise. If "cheapest in maintainer
attention" is applied item by item, anything requiring a human on the other end
is demoted forever, and the backlog converges on work that is comfortable rather
than work that matters. The rule has to be applied to the *portfolio*: prefer work
that produces outcomes the maintainer cannot produce alone, because those are the
outcomes that do not scale down with his available hours.

#416 is the clearest instance of that in the backlog.

## Why #416 specifically

The unresolved gap in front of Gittan right now is not a feature. It is that
there is no demo anyone can watch, and the maintainer is not the right person to
produce one. Two things are missing and only external users create both:

1. **Third-party proof.** Every claim about reconstructing a day currently rests
   on one machine and one person's config.
2. **Demo raw material.** Recordings of someone else's real first run are more
   convincing than a scripted walkthrough, and they cost the maintainer a call
   rather than a production effort.

#416 as written buys only the first. Its acceptance criterion is "one external
person has produced a report from their own data and given structured feedback."
Nothing in it captures the session, so the demo problem survives the issue being
closed. That is the actual defect in the ticket, and it is why demoting it looked
reasonable: at `next` **and** with no recording criterion, it was scoped as pure
cost.

## Decision

**Promote #416 to `priority:now`** and re-scope before starting:

- 2–3 testers from the maintainer's own network who actually run the CLI, not one
  committed tester. Two or three gives coverage of different setups and survives
  one dropping out.
- Add the missing acceptance criterion: each session produces **reusable demo raw
  material** (asciinema cast, screen recording, or a shared-screen capture the
  tester consents to), not only written feedback.
- Reuse what exists instead of building a demo path: `docs/runbooks/beta-onboarding-config.md`
  (the dry-run target), `docs/runbooks/repeatable-onboarding-demo.md`,
  `docs/runbooks/asciinema-expected-outcome-loop.md`, and #253 (Live Terminal
  Sandbox Demo, `priority:later`) as the eventual publishing surface.

### The order ahead of it holds

Promoting #416 does not jump it to the front, and the leak work is not competing
with it, it is a precondition:

1. **#431** — client names in committed docs. You cannot invite outsiders into
   the repo, or publish a recording made against this config, while real client
   names are in it.
2. **#515** — prevent client data reaching issues, PR bodies and comments. Same
   reason, forward-looking: testers filing issues is the new exposure surface.
3. **#414** — Chrome dashboard-work evaporation. A correctness bug a new tester
   hits on day one and reads as "the tool loses my time".
4. **#448** — Lovable Desktop open-app ≠ authorship. Same, ghost projects in a
   first report destroy trust immediately.
5. **#416** — external testers, with demo material as an output.

#431 and #515 gate #416 in the literal sense: do not schedule a tester session
until both are closed.

## Acceptance criteria (#416, revised)

```gherkin
Feature: External testers produce both proof and demo material

  Background:
    Given #431 and #515 are closed
    And docs/runbooks/beta-onboarding-config.md has been dry-run on a clean profile

  Scenario: A tester reconstructs a day from their own machine
    Given an external tester who has not seen Gittan configured
    When they run setup, doctor, and one report against their own data
    Then they produce a project-hour report from data the maintainer has never seen
    And they give structured feedback on the first three friction points

  Scenario: The session leaves reusable demo material
    Given a tester has consented to being recorded
    When the session runs
    Then a recording or cast of the first run is retained
    And it contains no client names, machine paths, or third-party data
    And it is usable as source material for a public demo without re-shooting

  Scenario: Coverage does not depend on one person
    Given testers are recruited from the maintainer's own network
    When at least two have completed a first run
    Then the issue can close even if a third never starts
```

## Flagged, not decided

Two `priority:later` items only pay off with sustained coding time and were
prioritized under the old capacity assumption. They need a deliberate
re-evaluation, which is its own pass and not this one:

- **#242** — Gittan → GitHub Marketplace app (hybrid, local-first-preserving).
- **#263** — Reported/approved time layer, phased backlog.

## Out of scope

No code, no collector changes, no release. The pass is complete when #416 carries
`priority:now`, its body reflects the revised scope and acceptance criteria, and
#513 carries a comment recording the reversal so the lineage stays readable.
