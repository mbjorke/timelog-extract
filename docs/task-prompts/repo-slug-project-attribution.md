# Worktree-invariant attribution via git remote/repo slug

## Problem

Project classification leans on the **working-directory path/leaf**. For git
worktrees this is fragile:

- A worktree under the project tree
  (`<project>/.claude/worktrees/<name>`) still has the project name in its
  path, so full-path classification happens to match. Safe today.
- A **sibling** worktree (our own `scripts/git_worktree.sh` creates worktrees
  next to the main clone) named without the project term in the path classifies
  to **Uncategorized**.
- The `dir`/`branch` **anchors** still carry the per-worktree leaf
  (`confident-hopper-fe58c2`, branch `claude/<name>`), which pollutes
  `unanchored_top_anchors` and `gittan map` suggestions.

A leaf-pattern heuristic cannot fix the anchor leak: a Claude worktree leaf
(`confident-hopper-fe58c2`, `<slug>-<hex>`) is byte-for-byte indistinguishable
from a real Lovable-renamed repo (`financing-portal-dev-31e799cf`). A
`<slug>-<hex>` filter therefore produces false positives on real projects and
was deliberately rejected. The only reliable signal is the **path** (a leaf
under `.claude/worktrees/`) or the **remote slug**, which this spec uses.

Git worktrees **share the same remote**, so the repo slug (`owner/repo`) is
identical across every worktree of a project — a stable, worktree-invariant
attribution key that the directory leaf is not.

## Validated evidence

- `git-worktrees.json` (Claude Code) maps each worktree → `baseRepo`, `branch`,
  `path`; all worktrees point at the same base repo.
- Claude Code session diff-stats are keyed by `<session>:<owner>/<repo>:<branch>`
  (the repo slug is present even inside a worktree).
- Claude Code `/events` payloads carry `owner/repo` per event regardless of
  which worktree the cwd points to.

## Task

1. Add a helper that resolves a working-directory path (or an event carrying a
   repo URL / `owner/repo`) to its **remote slug**, worktree-aware:
   - prefer an explicit `owner/repo` already present in the event,
   - else resolve the path's git repo and read `origin` remote → slug,
   - cache per-path so collectors don't shell out repeatedly.
2. Feed the slug into the classification haystack **before** the dir leaf, and
   expose it as a new `repo` anchor kind in the unified `top_signals` model
   (rule_type `match_terms`, since slugs match like terms).
3. Profiles: document that adding the GitHub slug (e.g. `owner/repo`) to a
   project's `match_terms` makes attribution worktree-proof. `gittan map`
   already suggests slugs from local clones — extend it to suggest the slug as
   the canonical anchor when worktree leaves are detected.
4. Keep the dir leaf as a fallback signal; do not remove it.

## Acceptance criteria

- Work done in a **sibling** worktree (path without the project term) is
  attributed to the correct project via its remote slug.
- Worktree `dir`/`branch` leaves no longer appear as unmapped anchors once the
  slug is mapped (the slug anchors the work).
- No regression for non-worktree work or projects without a git remote.
- Full autotest suite green; no Python file exceeds 500 lines.

## Non-goals

- No network calls to GitHub; slug comes from the **local** git remote config.
- Not changing how hours are computed — only how events attribute to projects.

## Traceability

- story_id: GH-pending
- spec_status: draft
- implementation_status: not built
- created_at: 2026-06-12
- last_updated_at: 2026-06-12
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: investigation in PR #140 thread (2026-06-11/12); worktree leaves observed leaking as anchors; repo slug shown stable across worktrees in git-worktrees.json, diff-stats keys, and /events payloads
- validation.decision: NO-GO
- changelog:
  - 2026-06-12: Initial draft from git-worktree attribution investigation.
