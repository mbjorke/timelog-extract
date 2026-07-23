# Task Prompt: Attribution signal — "was this me or my agent?"

Planning spec (product-owner pass). No code. Captures a **live discovery** and an
honest sizing decision: local cross-tool evidence can *corroborate* whether a git
action looks human-attended vs agent/CLI — useful as a **pitch demo / story
garnish**, not a vision pivot and not a fundable product thesis. Read product
framing in `docs/product/vision-documents.md` (precedence) before extending.

## Traceability

- story_id: `pending` (do **not** promote via `/docs-to-issues` until a later
  deliberate decision; current PO call is **no issue, no vision change**)
- spec_status: `draft`
- implementation_status: `not built`
- created_at: `2026-07-23`
- last_updated_at: `2026-07-23`
- implementation.pr: `pending`
- implementation.branch: `pending`
- implementation.commits: `[]`
- validation.evidence: `pending`
- validation.decision: `NO-GO` (sized down after maintainer market judgment —
  leading-indicator pain only; do not change vision or fundraise on this)
- changelog:
  - `2026-07-23: Initial draft from a live discovery (local browser presence near a merge).`
  - `2026-07-23: Demote vision change to do-not-build; correct investor section (garnish, not thesis); sanitize live identifiers; bound wording to signal not proof; add timezone decision; separate docs-to-issues from PO priority.`

## Why this exists (the discovery)

A real question came up: an external contributor's PR merged under the
maintainer's GitHub account, and the maintainer did not recall doing it. GitHub
could not answer "was it me or an agent?" — `mergedBy` shows the account whether
a human clicks merge or an agent runs `gh pr merge` with the same token.

Gittan's **local Chrome timeline** supplied corroborating presence: the browser
hit the same PR page **seconds before** the merge timestamp. That pattern is
*consistent with* a human merge (an agent/CLI merge typically leaves no such
visit). It is **not proof** — other browsers, cleared history, another machine,
or coincidental tabs can also produce presence or absence. Exact investigation
identifiers and wall-clock stamps stay in a non-committed local note; this
committed spec keeps only the evidence *pattern*.

## Positioning angle (story garnish — not a pivot)

Gittan is already sold as "tracks what you actually did **when AI does half the
work**." The discovery sharpens a **demo anecdote**, not a new product pillar:

> Local, timestamped, cross-tool evidence (browser, IDE, commits, mail) can
> **corroborate** whether an action under *your* identity looks human-attended
> vs agent/CLI. Cloud time-trackers and GitHub alone cannot see that local
> presence — that is a consequence of local-first design, not a new collection
> surface.

Honest scope: occasional forensics / pitch demo on data we already collect.
**Not** a daily surface. **Not** a reason to rewrite the vision docs.

## Backlog (ordered) — post sizing decision

### `do not build yet` — vision / positioning change
- Do **not** add "me vs my agent" attribution framing to
  `docs/product/gittan-vision.md`, the English companion, or root `VISION.md`.
  Changing vision is a strategic bet that needs a real market check first; the
  maintainer's judgment (2026-07-23) is that the pain is a **leading indicator**
  (rare outside heavy multi-agent workflows on owned repos), not mass demand.
  Keep this file as the recorded "we considered and sized it down" artifact.

### `later` — optional `whodunit` surface (exploratory; gated)
- A `gittan whodunit` / attribution mode: given a git action (commit/merge SHA or
  a timestamp), report whether local presence evidence in a window is
  **consistent with human presence**, **consistent with agent/CLI** (no local
  presence), or **unknown**. Gherkin below. Do not start without an explicit
  later prioritization — and never treat a green demo as product validation.

### `do not build yet` — proof / court-grade claims
- Any tamper-proofing, cryptographic attestation, or "legally admissible"
  claim. This is a **signal, not proof** (see non-goals). Overclaiming certainty
  would break trust — the opposite of the product's promise.
- Attribution of *other people's* actions. Only the local user's own activity.

## Acceptance criteria / Gherkin (for the gated `later` feature)

```gherkin
Feature: Corroborate a git action with local human-vs-agent presence signals

  Background:
    Given Gittan has local activity evidence (browser history, IDE events, commits)
    And the check is read-only and never leaves the machine
    And all timestamps are normalized to a single timezone before correlation

  Scenario: Local presence near the action → consistent with human
    Given a merge/commit occurred at a known instant
    And local browser or IDE activity touched the same repo/PR within the window
    When I run the attribution check for that action
    Then it reports "consistent with human presence" with corroborating timestamps
    And it states this is a signal, not proof

  Scenario: No local presence near the action → consistent with agent/CLI
    Given a merge/commit occurred at a given timestamp
    And no local browser/IDE presence exists within the window
    When I run the attribution check
    Then it reports "no local presence — consistent with an agent or CLI action"
    And it explains gaps that could also cause absence (other browser, cleared history)

  Scenario: Insufficient evidence → honest "unknown"
    Given local history does not cover the action's date
    When I run the attribution check
    Then it reports "unknown — no local evidence in range" and never guesses
```

## Non-goals
- Not a daily feature. Occasional, on-demand forensics / pitch demo.
- **Not proof.** Absence of local evidence is not proof of an agent (different
  browser, cleared history, another machine). Presence is corroboration, not a
  verdict. The surface must say so.
- **Not a vision pivot.** Do not rewrite product vision around attribution.
- No new collection. Reuses existing sources; no new consent surface beyond what
  those sources already carry (`docs/specs/source-evidence-policy.md`).
- Local-first only — nothing leaves the machine.

## Decisions needed before building the `later` feature
1. **Window size** for "presence near the action" (e.g. ±5 min) and whether it
   scales by source (a browser visit is tighter evidence than an open IDE).
2. **Which sources count as presence** and their weight (browser visit to the
   exact URL > IDE focus > generic activity). Reuse evidence weighting from
   `docs/specs/source-evidence-policy.md` rather than inventing a scale.
3. **How confidence is expressed** — plain "consistent with human / no presence /
   unknown", not a false-precision percentage. Avoid "attest" / "confirmed" /
   "ground truth" wording in user-facing copy.
4. **Input shape** — commit/merge SHA (resolve its timestamp) vs a raw timestamp;
   how the action's repo/PR is matched to browser URLs.
5. **Timezone normalization** — git / GitHub action times are typically UTC;
   Gittan's rendered timeline uses local wall time. Correlation must normalize
   before comparing, or a same-second event looks like a multi-hour miss.

## Investor / financier narrative (corrected)

**Do not treat attribution as a fundraising thesis.** Early wording that this
"reframes the natural funder" toward big AI / security / AI-governance was
over-optimistic: those segments build attribution internally at scale and are
unlikely buyers of a solo GPL local-first tool.

Honest framing:
- Natural support for a **local-first + GPL** hours product remains ethos-aligned
  sponsors / users who care about privacy and "what you actually did" — driven by
  the **daily hours** value, not by attribution forensics.
- Attribution is a **story garnish**: a memorable demo anecdote in a pitch
  ("local evidence corroborated human vs agent within seconds"), not a
  standalone fundable product and not a reason to expect big-AI funding.

Lead with the hours product. Keep this discovery as optional color. Do not pitch
attribution as the core until (and unless) real demand is shown — and the
2026-07-23 sizing call is that demand is not there yet for a vision change.

## Next step in the PO flow
- **Do not** run `/docs-to-issues` for this spec right now (no board issue until
  a later deliberate pick-up).
- **Do not** change vision docs from this PR.
- If a future pass prioritizes the gated `later` feature: `/docs-to-issues`
  creates or syncs the GitHub issue only; then apply priority labels via
  `docs/skills/gittan-product-owner.md` (creation and priority are separate
  steps — do not imply the generator does both).
