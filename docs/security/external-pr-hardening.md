# External PR hardening

Two layers defend `main` against external/fork pull requests. They are
complementary; neither replaces the other.

## Layer 1 — auto-merge author-gate (code, shipped in #441)
`scripts/rabbit_loop.sh --author-gate` blocks auto-**merge** of any PR whose
author is not an allowlisted internal identity, or that comes from a fork. It is
the gate on the *merge* path.

## Layer 2 — triage at open (code, this PR / #442)
`.github/workflows/external-pr-triage.yml` runs on `pull_request_target`
(opened/reopened) for **fork PRs only**. It reads **metadata only** — it never
checks out or runs the fork's code — and:

- labels the PR `external:needs-review` and comments that external PRs are
  reviewed by a maintainer and never auto-merged (cc's the repo owner);
- **narrowly auto-closes** only the high-confidence link-rot spam signature
  (docs-only + a "broken/dead link" claim + a diff line adding a
  `web.archive.org` snapshot — the probe pattern from PR #433/#443). Everything
  else is labelled and left open, so a genuine first-time contributor is never
  slammed.

The spam/needs-review decision lives in `scripts/external_pr_triage_classify.py`
(pure, unit-tested in `tests/test_external_pr_triage.py`), so the signature can be
tuned and tested without touching the workflow.

## Layer 3 — GitHub settings (maintainer-only, cannot be scripted here)
Apply these in the repo settings; a workflow cannot set them for you:

1. **Settings → Actions → General → Fork pull request workflows**: require
   approval for **all outside collaborators** (or first-time contributors) before
   any workflow runs on their PR. This is the primary containment for
   `pull_request_target`/CI on forks.
2. **Branch protection / ruleset on `main`**: require a maintainer review before
   merge, and keep "require conversation resolution" on, so no external PR merges
   without a human. (Solo-maintainer note: do not set "require N approvals" if you
   cannot self-approve — use required review + the layers above instead.)

## Why this is safe
`pull_request_target` grants a privileged token in the base-repo context. The
workflow's guardrails: it checks out only the **base** commit (never the fork
head), passes all PR-authored text through `env:` (never interpolated into the
shell), reads changed files/patches via the API (diff text, not executed code),
and requests only `pull-requests`/`issues: write`. Getting any of these wrong is a
worse hole than the probe it defends against — review changes to this workflow
carefully (`.github/` is a NEEDS_HUMAN surface).
