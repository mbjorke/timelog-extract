# TIL: Review tasks are documents, not code

**Date:** 2026-04-11  
**Area:** Orchestration — task scope  
**Agent:** Claude (claude/gittan-launch-review-4a5DD)

## What happened

An agent was given a launch review brief: answer a set of questions about code quality
and business strategy, and produce a document. While reading the codebase, it found a
security issue (SQL injection in `collectors/chrome.py`). It fixed the issue, then
wrote the review document — both in the same commit.

Marcus cherry-picked the fix into `main` manually (PR #14). The review branch was never
evaluated as a proper PR because its scope was muddled: was it a review, or a bugfix?

## The lesson

**An agent that finds something interesting while reviewing will want to fix it.** That
impulse is useful in an implementation task and harmful in a review task. The agent
isn't being lazy or negligent — it's being helpful in the wrong register.

The solution is not to suppress the impulse but to redirect it: findings go into the
document, not into the diff. The document then becomes the gate for whether a fix
follows.

This also has a practical orchestration consequence: **a mixed-scope branch is hard to
evaluate and easy to set aside.** A clean review document in its own commit can be
merged, discussed, or rejected on its merits. A review-plus-fix bundle requires the
maintainer to disentangle two things before deciding.

## What changed

- `AGENTS.md` — **Do not #1** added to the top-level prohibition table; "Task types —
  read the brief before acting" section added with full explanation.
- `CLAUDE.md` — "Task types and scope discipline" section added.

## Orchestration pattern

> When assigning a review task to an agent, the brief should explicitly say:
> "Your output is a document. Note findings; do not implement them."
>
> If you want both a review and a fix, say so, and ask for separate commits.
