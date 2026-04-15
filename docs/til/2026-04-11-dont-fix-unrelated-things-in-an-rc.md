# TIL: Don't fix unrelated things when starting an RC

**Date:** 2026-04-11  
**Area:** Orchestration — RC scope discipline  
**Agent:** Claude (claude/gittan-launch-review-4a5DD)

## What happened

A review/RC branch was opened for a launch review. The agent found a SQL injection
vulnerability in `collectors/chrome.py` while reading the codebase, fixed it, and
committed it alongside the review document — all in the same branch and same commit.

The fix was correct. The review document was correct. But they were bundled together,
and the branch scope became unclear: was this a review, a security fix, or both?

Marcus cherry-picked the fix into `main` via PR #14. The review document never got a
formal evaluation cycle. A CodeRabbit review on the PR then added further suggestions
(wildcard escaping, unit tests) that got applied — all reasonable in isolation, but
each one deepening the scope drift from the original brief.

## The lesson

**An RC or review branch has a defined scope. Finding something unrelated does not
expand that scope.**

The temptation to fix things you find is strong — the issue is right there, the fix
is obvious, it seems wasteful not to do it. But:

1. The fix changes what the PR is about, making it harder to evaluate each part.
2. Every additional change invites more review (CodeRabbit, maintainer) on the
   unrelated work, pulling the branch further from its original purpose.
3. "It worked out" (the fix landed) is a bad feedback signal — it masks the
   process failure and reinforces the behaviour for next time.

**The right move:** note the finding clearly, finish the scoped work, push, then open
a *separate* branch for the fix. Two clean PRs beat one muddled one every time.

## The maintainer side of this

Scope discipline is a two-sided contract. When an agent overreaches and the maintainer
accepts the work anyway — clicking merge, applying CodeRabbit suggestions, moving on —
the message received is that mixed-scope branches are acceptable.

If an agent pushes a branch that contains out-of-scope work, the cleaner response is:
*"Split the fix into its own commit / branch. I will merge the review document first."*

## What changed

- `AGENTS.md` — **Do not #1** and "Task types" section.
- `CLAUDE.md` — "Task types and scope discipline" section.
- `docs/incidents/2026-04-11-unrelated-fix-bundled-into-review-branch.md`

## Orchestration pattern

> When briefing an agent on an RC or review task, say explicitly:
> *"If you find issues outside the scope of this task, record them and stop.
> Do not fix them on this branch."*
>
> When reviewing an agent's PR, if it contains out-of-scope work, ask for a split
> before merging — even if the work is correct.
