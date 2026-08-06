# Prevent client data reaching issues, PR bodies and comments

Stop new leaks on the surfaces `#429`'s guard structurally cannot see. Cleanup
of what already leaked is `#431`; this is the forward-looking half, and the
maintainer's stated priority between the two.

## Traceability

- story_id: `GH-515` (https://github.com/mbjorke/timelog-extract/issues/515)
- spec_status: approved
- implementation_status: not built
- created_at: 2026-08-06
- last_updated_at: 2026-08-06
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO (not built)
- changelog:
  - 2026-08-06: Bot amplification found on #431 — one CodeRabbit reply held 278
    of the thread's occurrences. `issue_comment` moved into the first slice;
    app authors explicitly in scope. Recorded the MIN_TERM_LEN=4 blind spot.
  - 2026-08-06: Initial draft. Split from #431 after finding ~278 term
    occurrences in that issue's own comment thread vs ~22 lines in `docs/`.

## Problem

`scripts/check_docs_no_client_data.py` (#429) is sound and correctly reasoned:

> Right layer is **pre-commit** (it has the local config; CI does not, since the
> config is gitignored).

That reasoning holds for files. It also means the guard covers exactly one
surface — the working tree — and every leak found on 2026-08-06 was outside it:

| Surface | Passes through git? | Guarded |
| --- | --- | --- |
| `docs/*.md` | yes | ✅ pre-commit |
| Issue body | no | ❌ |
| Issue / PR comment | no | ❌ |
| PR description | no | ❌ |

#431's own thread carries roughly **278 occurrences** across six terms — more
than ten times the docs surface it was opened to track — and its body listed
them in clear under a "(masked terms)" heading until it was corrected.

**Three things make this worth automating rather than writing a rule about.**

First, the leak arrives by paste. Someone runs a report on their own machine
and pastes the output into an issue to explain what they saw. No discipline
survives that reliably, and the maintainer has explicitly less time for
discipline going forward.

Second — and this is the one that changes the design — **the review bot
amplifies it**. #431's body listed a handful of terms. CodeRabbit's
auto-generated *Coding Plan* reply quoted them **278 times** across 52 code
blocks, roughly a fortyfold multiplication of a small human mistake. A guard
scoped to human-authored text would have watched the six and missed the 278.

Third, **agent sessions cannot self-check.** A hosted Claude or Cursor session
has no access to `~/.gittan/timelog_projects.json` — it is local, gitignored,
and on a different machine. Agents author a large share of this repo's issue
and PR text. For that content, a server-side check is not the convenient place
for the guard; it is the *only* place one can exist.

## Non-goals

- Cleaning up existing leaks — that is #431.
- Rewriting git history.
- Committing the term list in any form. A denylist of client names in the repo
  is the same leak with extra steps.
- Auto-editing anyone's issue or comment. The check reports; a human edits.
- Blocking issue creation. A false positive that prevents filing a bug is worse
  than a flagged one that gets edited a minute later.

## Behavior

```gherkin
Scenario: A new issue body containing a client term is flagged
  Given the repository holds the private term list as an Actions secret
  When an issue is opened whose body matches one of those terms
  Then a bot comment names the count and the field it matched in
  And the issue is labelled privacy:review
  And no matched term appears anywhere in the comment or the run log

Scenario: A clean issue is left alone
  Given an issue body matching no private term
  When it is opened
  Then no comment is posted and no label is added

Scenario: An edit that removes the term clears the flag
  Given a flagged issue
  When its body is edited so no term matches
  Then the privacy:review label is removed

Scenario: A fork without the secret degrades to skipped, never to a leak
  Given a repository or run with no term list configured
  When the check runs
  Then it exits successfully having checked nothing
  And it says so, so a silent pass is not mistaken for a clean result
```

## Design decisions to confirm before implementing

**1. Where the term list lives — Actions secret.**
`#429` concluded CI cannot hold the terms because the config is gitignored. A
repository secret breaks that constraint: it is not in the tree, not in the
diff, and not readable from a fork. Proposal: `PRIVACY_TERMS`, newline- or
comma-separated, mirroring what `check_docs_no_client_data.py` derives from
`timelog_projects.json`. Cost: it is a second copy that must be refreshed when
a project is added — name the refresh trigger, or accept staleness as
acceptable for a guard whose purpose is catching the obvious case.

**2. Bot comments count.** The check must not skip `github-actions[bot]`,
`coderabbitai[bot]` or any other app author. The instinct to ignore bot noise is
exactly backwards here — the bot produced 98% of the exposure on #431.

**3. The check must never echo a match.** Output is a count and a field name,
never the term, not even partially. Workflow logs on a public repo are public.
A leak detector that prints the leak is worse than no detector, and `#431`'s
body is the proof — it printed the terms while claiming to mask them.

**4. Trigger surface — issues *and* comments in the first slice.**
This was originally scoped to `issues: [opened, edited]`, on the reasoning that
it covers "the surface where the damage was measured". That was wrong: the
damage was measured in an `issue_comment`, and a check on issue events alone
would have caught none of the 278 occurrences. Both triggers ship together.

`pull_request_target` remains a later slice, and carefully — it carries secrets
into a fork-triggered context and must never check out fork code.

**5. Reuse the matching logic, not a copy.** `check_docs_no_client_data.py`
already has `DEFAULT_ALLOW`, `MIN_TERM_LEN`, and masking. Factor the matcher so
both entry points share it. Two implementations of "what counts as a term" will
drift, and the drift will be discovered by a leak.

## Acceptance

- An issue **or comment** carrying a term from the secret is labelled and
  reported within one workflow run, whether its author is a human or an app.
- A three-character term is either detected, or its non-detection is a stated,
  documented limit rather than a surprise (see below).
- Neither the comment nor the workflow log contains the term, at any length.
- An issue with no match produces no comment, no label, no noise.
- Editing the term out removes the label.
- With the secret unset, the workflow exits 0 and states that it checked
  nothing.
- The term-matching logic has one implementation, shared with the pre-commit
  guard.

## Validation

- Fixture tests over the shared matcher, using neutral placeholders
  (`project-alpha`, `customer-a.test`) — never a real term, in the test or the
  fixture.
- One live check on a throwaway issue in this repo using a deliberately
  planted, non-client term in the secret; confirm the comment, the label, and
  that the term appears in neither the comment nor the run log.
- Confirm the fork path by running the workflow with the secret unset.

## Known limit inherited from the matcher

`check_docs_no_client_data.py` sets `MIN_TERM_LEN = 4` to keep false positives
down. One of the six terms on #431 is **three characters**, so the guard could
never have flagged it — it was cleaned only because it happened to be written
out by hand in the issue body.

Short client codes are therefore invisible to this design, not merely missed by
it, and the same hole is inherited by anything built on the shared matcher.
Decide before implementing: lower the floor and absorb the false positives, keep
a short-code list that is exact-match and case-sensitive, or state the limit
plainly so nobody trusts a clean result more than it deserves.

## Dependencies

- `#429` — the guard and its matcher. Merged.
- `#431` — the cleanup. Independent: this prevents new leaks whether or not the
  old ones are cleaned, and cleaning without this leaves the surface open.

## Note on the generator path

`/docs-to-issues` builds issue bodies from `docs/task-prompts/*.md`, which are
already covered pre-commit. That path is therefore mostly safe already — a
clean spec produces a clean issue. It is the hand-written and pasted bodies
that are unguarded, which matches where the occurrences were found.
