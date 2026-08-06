# Shared rules — every Jules persona

Status: active
Last updated: 2026-08-06

Applies to Bolt, Palette **and** Sentinel. Read this before any work, every run.

## Blocking pre-work checks, in order

**1. List the open PRs on `mbjorke/timelog-extract`.**
If you cannot list them, end the run without opening a PR. That is a *successful*
run, not a failure. Do not proceed on assumption.

**2. Does any open PR touch the files you intend to change?**
Then do not open a new PR. Push to that branch, or answer its review threads,
and stop.

**3. Does your persona already have 2 or more open PRs?**
Then do zero new work. Spend the entire run answering CodeRabbit and Greptile
threads on them, then stop.

**4. Before fixing anything, verify the problem still exists on current `main`
*and* is not already fixed in an open PR.**
A problem with a fix waiting in review is not an open problem. Scanning `main`,
finding an unfixed file, and fixing it is exactly how the same
`briox_connection_test.py` hardening got written seven times (#481, #484, #487,
#493, #496, #500, #503).

## Output limits

- **At most one PR per run.**
- **Most runs should end with no PR at all.** That is the expected outcome, not
  an idle run. Never open a PR merely to have produced something.
- **A `.jules/` journal edit is not a PR.** If your only change is to
  `.jules/*.md`, do not open a pull request — #505 was titled "harden HTTPS
  openers" and contained nothing but a five-line journal note.
- Different code reaching the same product outcome is still a duplicate.

## Finishing

A scheduled run cannot wait for review bots, so "done" is a *declared handoff*.
End every run that touched a PR with one comment:

```markdown
## Handoff (<Persona>, YYYY-MM-DD)
- **Done:** <what changed, one line per item>
- **Verified:** <exact commands run + actual result — not "should work">
- **Not done / skipped:** <deliberate omissions + why>
- **Awaiting:** CodeRabbit / Greptile review; next run answers them.
```

The two review bots active on this repo are **`coderabbitai`** and
**`greptile-apps`**. Qodo is referenced in older docs but does not run here —
do not wait for it.

Next run, before anything else: give every new review finding a disposition —
fix it and reply with the commit, or reply with one sentence on why not.
Silence is not a disposition.

Do not merge your own PRs and do not act as finisher for another agent's PR.

If you need to know whose branch you are looking at, read **commit** authorship,
not the pull request author. Every PR on this repo reports `mbjorke` regardless
of which agent produced it, because they all push through the maintainer's
credentials. Commits are honest: `google-labs-jules[bot]`, `Cursor Agent`,
`Claude`. A branch carrying more than one of those has already been worked on by
someone else — leave it alone rather than pushing over their changes.

## Never rewrite a fix that answered a review thread

If a commit you did not author is the reply to a review finding, it is settled.
Do not restate it, tidy it, or replace it with your own version of the same
idea. Reply in the thread if you disagree; do not push over it.

Two rules follow from that, and both are absolute:

**Never delete a test.** Not to simplify it, not to fold it into another case,
not because it looks redundant. A test written against a review finding is the
only thing keeping that finding fixed. On #499 the same two tests were deleted
three times, including
`test_report_with_all_events_alias_keeps_report_guidance` — the regression test
for the exact defect that PR existed to fix.

**Never delete a comment that explains why.** A comment saying "not X, because
X breaks Y" is what stops the next run from re-introducing X. Deleting it and
keeping the code is how a fix survives one round and dies the next.

## A test that cannot fail is worse than no test

Before adding or changing a test, break the code it covers and confirm the test
goes red. If it stays green, it is decoration and it will hide the next
regression.

Two shapes that pass while proving nothing, both seen on this repo:

- **One mock shared across cases.** `assert_any_call` matches *cumulatively*, so
  case 5 is satisfied by the call case 2 made. Either use `reset_mock()` between
  cases or read `call_args` per case — better, split them into separate test
  methods.
- **Mocking the thing under test.** Patching `print_command_hero` and asserting
  it was called cannot observe that `print_command_hero` resolves an unknown
  name to the wrong hero. Assert on the rendered result, not on the call.
