# TIL: A CodeRabbit checkbox is a scope decision

**Date:** 2026-04-12  
**Area:** Orchestration — maintainer review discipline  
**Actor:** Marcus (PR #14 review)

## What happened

PR #14 contained an out-of-scope security fix bundled with a review document. CodeRabbit
reviewed the PR and suggested adding unit tests for the security fix. Marcus clicked
"Add unit tests" in the CodeRabbit chat interface.

That single click started a six-commit cascade: tests were generated, CI failed due to
the 500-line file policy, Cursor was brought in to split the test files, CodeRabbit
reviewed the split and asked for better assertions, Cursor applied those too, then added
PyPI release notes as context.

Every individual action was correct. The cascade was invisible until the whole sequence
was laid out.

## The lesson

**Every CodeRabbit suggestion you click on an out-of-scope PR is a vote to keep that
scope.** CodeRabbit reviews code as presented — it does not know what the branch was
supposed to be for. Its suggestions are technically sound. The question of whether to
act on them is a scope question, not a code quality question.

Before clicking any suggestion on a PR:

1. Is this PR's scope still what it was supposed to be?
2. If not — does acting on this suggestion help or deepen the drift?

The "Add unit tests" click was a reasonable response to a security fix. It was the
wrong click on a branch that shouldn't have had a security fix in the first place.

## The cascade shape

Out-of-scope work invites review. Review invites suggestions. Suggestions, when
applied, generate new work (CI, further review). Each step is locally justified. The
original scope becomes unrecoverable without deliberate intervention.

This is distinct from scope creep by addition (adding features). This is **scope
creep by review** — the review tooling itself is the mechanism of drift.

## What changed

- `docs/incidents/2026-04-12-coderabbit-checkbox-cascade-on-out-of-scope-pr.md`
- `AGENTS.md` — Do not #1b notes the maintainer side of this.

## Orchestration pattern

> When a PR contains out-of-scope work, do not engage with CodeRabbit suggestions
> on that work. Instead: ask the agent to split the branch, then review each part
> separately.
>
> If you have already clicked a suggestion, assess whether the resulting work can be
> cleanly separated. If not, accept the cascade and document it — but treat it as a
> process failure, not a success.
