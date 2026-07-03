# Idea — kanin handoff board close-out (read human verdict)

**Status:** Idea only — not implemented. Related: #240, #272, `scripts/rabbit_handoff.sh`, `docs/skills/rabbit-loop.md`.

## Problem

`rabbit_handoff.sh` is **write-only** toward GitHub Projects today:

1. NEEDS_HUMAN + CONVERGED → move linked **issue** to **Needs manual testing** + post checklist comment.
2. Human runs checklist and posts results (e.g. `Manual test verdict: PASS` on the issue).
3. Human **manually** moves the board card to **Done** (or **In progress** if the issue stays open for more scope).

The loop does **not** read comments, interpret PASS/FAIL, or close out the board column. PRs (e.g. #278) are **not** added to the board unless someone adds them — the board is issue-centric; handoff only targets `--issue N`.

Observed 2026-07-02: #240 handoff ran, manual PASS was posted, but Status drifted (e.g. back to Ready) until the maintainer moved it manually. Follow-up PRs can “skip the backlog” entirely if no issue is linked and no agent adds them to the project.

## Proposed direction (future)

Optional **`rabbit_handoff.sh --complete --issue N`** (name TBD):

- Preconditions: issue was previously handed off (board item exists); optional machine stamp (e.g. comment template or label `kanin:manual-pass`).
- Human-triggered or maintainer-triggered — **not** inferred blindly from any comment (avoid false positives when an issue is partially done but stays open).
- Action: set project **Status → Done** (or a new column **Manual verified**), post a short close-out comment linking commit/PR merge SHA.
- **Out of scope for v1:** parsing free-form comments with an LLM; prefer an explicit verdict line or checkbox in the checklist template.

## Relationship to #272

Issue `#272` (agent↔task ownership) addresses **who** owns a branch. This idea addresses **when** the board reflects that manual verification finished — complementary, not duplicate.

## Acceptance sketch (if built)

```gherkin
Scenario: Maintainer closes handoff after explicit PASS
  Given issue #N is in "Needs manual testing" with a posted checklist
  When the maintainer runs rabbit_handoff.sh --complete --issue N
  Then the project Status moves to Done (or agreed close-out column)
  And a comment records the close-out with timestamp and optional PR link
```

## Until then (runbook)

- After manual PASS: move the **board card** yourself; keep the **issue** open/closed per remaining scope.
- For PR-only work: add the PR to the project manually or link a tracking issue.
- Agents: do not assume comments update the board; document Status changes in the PR thread when you move cards.
