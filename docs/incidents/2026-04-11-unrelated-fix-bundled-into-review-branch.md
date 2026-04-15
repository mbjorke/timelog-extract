# Incident: Unrelated fix bundled into review/RC branch

**Date:** 2026-04-11  
**Branch:** `claude/gittan-launch-review-4a5DD`  
**Status:** Partially resolved (fix landed in PR #14; review never evaluated as a review)

## Summary

An agent was given a launch review task — answer a set of questions about code quality
and business strategy, produce a document, commit it. While reading the codebase, the
agent found a SQL injection vulnerability in `collectors/chrome.py`. Instead of
recording it as a finding, the agent fixed it and bundled the fix into the same commit
as the review document.

The branch was never evaluated as a proper review PR. Marcus cherry-picked the security
fix into `main` manually (PR #14). The review document landed but never received a
review cycle on its own merits.

## Fault question

Both agent and maintainer share responsibility:

**Agent fault:** the brief was a review task. The agent correctly identified it as
such, wrote the document, but could not resist fixing an issue it found. This is a
scope discipline failure — acting outside the brief without confirmation.

**Maintainer fault (possible):** once the mixed-scope branch was pushed, Marcus may
have approved the fix via a CodeRabbit suggestion or PR merge rather than asking the
agent to split the commits. Accepting mixed-scope work normalises it. A cleaner
response would have been: "split the fix into a separate commit / separate PR, then I
will evaluate the review document on its own."

The ambiguity in fault is itself an orchestration lesson: **when an agent overreaches
and the maintainer accepts it anyway, the policy failure is reinforced on both sides.**

## Impact

- Review document produced but never formally evaluated.
- Security fix landed correctly but via an ad-hoc cherry-pick rather than a clean PR.
- Branch `claude/gittan-launch-review-4a5DD` sits unmerged, its scope unclear.
- Agent learned the wrong lesson: "it worked out" rather than "I was out of scope."

## Root cause

No explicit rule in `AGENTS.md` or `CLAUDE.md` said: *do not fix code during a review
task.* The agent defaulted to "helpful" behaviour without a policy guardrail.

## Corrective actions

- `AGENTS.md` — "Task types — read the brief before acting" section added.
- `AGENTS.md` — **Do not #1** added to the top-level prohibition table.
- `CLAUDE.md` — "Task types and scope discipline" section added.
- `docs/til/2026-04-11-review-tasks-are-documents-not-code.md` — orchestration pattern
  documented.

## Open question

When CodeRabbit reviews a mixed-scope PR, it reviews the code as presented — it has
no awareness that part of the PR was out of scope. Clicking "apply fix" on a
CodeRabbit suggestion during a review-task PR deepens the scope problem rather than
correcting it. The maintainer's checkbox is the last gate; it is worth pausing before
approving suggestions on a PR whose scope is already muddled.
