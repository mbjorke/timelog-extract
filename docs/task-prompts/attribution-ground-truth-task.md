# Task Prompt: Attribution ground-truth — "was this me or my agent?"

Planning spec (product-owner pass). No code. Frames a positioning angle and a
behavior-ready backlog for a **local attribution / "whodunit"** capability that
falls out of data Gittan already collects. Read product framing in
`docs/product/vision-documents.md` (precedence) before extending.

## Traceability

- story_id: `pending` (promote to `GH-N` via `/docs-to-issues` only when an item is prioritized to `now`/`next`)
- spec_status: `draft`
- implementation_status: `not built`
- created_at: `2026-07-23`
- last_updated_at: `2026-07-23`
- implementation.pr: `pending`
- implementation.branch: `pending`
- implementation.commits: `[]`
- validation.evidence: `pending`
- validation.decision: `NO-GO` (exploratory wedge — validate the positioning before building the feature)
- changelog:
  - `2026-07-23: Initial draft from a live discovery — Gittan's Chrome timeline attributed a real PR merge to a human vs an agent.`

## Why this exists (the discovery)

A real question came up: an external contributor's PR (#293) merged under the
maintainer's GitHub account, and the maintainer did not recall doing it. GitHub
could not answer "was it me or an agent?" — it shows `mergedBy: mbjorke` whether
a human clicks merge or an agent runs `gh pr merge` with the same token.

Gittan's **local Chrome timeline** answered it: the browser hit
`.../pull/293` at `10:07:33Z`, **9 seconds before** the merge at `10:07:43Z`.
That browser presence in the exact moment is a human fingerprint — an agent/CLI
merge leaves no such visit. Conclusion: human merge, confirmed from local data
that no cloud tool holds.

## Positioning angle (this sharpens the existing story)

Gittan is already sold as "tracks what you actually did **when AI does half the
work**." The discovery sharpens it from a quantity question to an **attribution**
one:

> Gittan is the **local ground-truth of your own activity** — a timestamped,
> cross-tool record (browser, IDE, commits, mail). In a world where agents act
> under *your* identity, that local record is the only thing that can answer
> **"was this me, or my agent?"**

Why it is differentiated: no cloud tool can do this. Toggl/Timely never see your
local browser/IDE presence; GitHub/Jira only see the token action. Gittan's
**local-first** design — until now framed as a privacy feature — is precisely
what makes attribution possible.

Honest scope: this is a **wedge and a story on data we already collect**, not new
collection and not a pivot. It is occasional forensics, not a daily surface.

## Backlog (ordered)

### `now` — the narrative (free; it is only messaging)
- Add the "me vs my agent" attribution framing to `docs/product/gittan-vision.md`
  (and the English companion), and refresh the root `VISION.md` manifesto if the
  pillar wording changes. **Acceptance:** one paragraph names local attribution as
  a differentiator, consistent with the local-first / evidence-aggregation pillars;
  no contradiction with `docs/security/privacy-security.md`.

### `later` — the feature (exploratory wedge, not a daily driver)
- A `gittan whodunit` / attribution mode: given a git action (commit/merge SHA or
  a timestamp), report whether local presence evidence in a window suggests a
  **human** actor vs an **agent/CLI**. Gherkin below. Do not start until the `now`
  positioning item has been validated (does the story resonate with users/funders?).

### `do not build yet`
- Any tamper-proofing, cryptographic attestation, or "court-grade / legally
  admissible" claim. This is a **signal, not proof** (see non-goals). Overclaiming
  certainty would break trust — the opposite of the product's promise.
- Attribution of *other people's* actions. Only the local user's own activity.

## Acceptance criteria / Gherkin (for the `later` feature)

```gherkin
Feature: Attribution of a git action to a human vs an agent from local activity

  Background:
    Given Gittan has local activity evidence (browser history, IDE events, commits)
    And the check is read-only and never leaves the machine

  Scenario: Human presence near the action → likely human
    Given a merge/commit occurred at 2026-07-04T10:07:43Z
    And local browser or IDE activity touched the same repo/PR within the window
    When I run the attribution check for that action
    Then it reports "human presence evidence" with the corroborating timestamps
    And it states this is a signal, not proof

  Scenario: No local presence near the action → likely agent/CLI
    Given a merge/commit occurred at a given timestamp
    And no local browser/IDE presence exists within the window
    When I run the attribution check
    Then it reports "no local presence — consistent with an agent or CLI action"
    And it explains the gaps that could also cause absence (other browser, cleared history)

  Scenario: Insufficient evidence → honest "unknown"
    Given local history does not cover the action's date
    When I run the attribution check
    Then it reports "unknown — no local evidence in range" and never guesses
```

### Acceptance criteria for the `now` positioning item
- The attribution framing appears in the vision doc as a differentiator, tied to
  the existing local-first + evidence pillars (not a new pillar).
- Wording passes the privacy guardrail: nothing implies collecting others' data or
  sending anything off-machine.
- `VISION.md` manifesto refreshed only if pillar wording changes (per precedence).

## Non-goals
- Not a daily feature. Occasional, on-demand forensics.
- **Not proof.** Absence of local evidence is not proof of an agent (different
  browser, cleared history, another machine). Presence is corroboration, not a
  verdict. The surface must say so.
- No new collection. This reuses existing sources; no new consent surface beyond
  what those sources already carry (`docs/specs/source-evidence-policy.md`).
- Local-first only — nothing leaves the machine; consistent with the privacy guardrails.

## Decisions needed before building the `later` feature
1. **Window size** for "presence near the action" (e.g. ±5 min) and whether it
   scales by source (a browser visit is tighter evidence than an open IDE).
2. **Which sources count as presence** and their weight (browser visit to the exact
   URL > IDE focus > generic activity). Reuse evidence weighting from
   `docs/specs/source-evidence-policy.md` rather than inventing a scale.
3. **How confidence is expressed** — plain "human presence / no presence / unknown",
   not a false-precision percentage.
4. **Input shape** — commit/merge SHA (resolve its timestamp) vs a raw timestamp;
   how the action's repo/PR is matched to browser URLs.

## Investor / financier narrative implication

This reframes **who the natural funder is**. As a time-tracker, Gittan competes in
a crowded, low-margin productivity category (Toggl/Timely comparables). As the
**local attribution / ground-truth layer for the agent era**, the natural funder
shifts toward **developer-tooling, security/audit, and AI-governance** — segments
that are actively looking for "prove what a human vs an agent did" primitives as
agents get write access to repos, mail, and money.

The pitch is not "another time-tracker with AI." It is: *agents now act under your
identity across every tool; Gittan is the local record that can tell you — and
later, attest to others — which actions were actually yours.* That story is
GPL-friendly, local-first, and rides the same evidence-aggregation moat already
described in the vision docs; it just points it at accountability, not only hours.

Honest caveat for any deck: lead with the **hours** product (proven, daily value);
use attribution as the **wedge/differentiator** that explains why local-first wins
in the agent era. Do not pitch attribution as the core product until the `now`
positioning item is validated with real users/funders.

## Next step in the PO flow
When the `now` positioning item is picked up, create its issue via
`/docs-to-issues` and set `priority:now`; leave the `later` feature in this spec
only until the story is validated. See `docs/skills/gittan-product-owner.md`.
