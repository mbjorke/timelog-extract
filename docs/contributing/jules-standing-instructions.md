# Standing instructions for Jules (Bolt / Palette)

**Audience:** Google Jules scheduled Bolt and Palette runs on this repo.  
**Why this exists:** Daily briefs reopened the same work as new PRs without
looking at the open queue (#374–#386 Bolt, #375–#387 Palette), and a post-review
commit on #386 reintroduced a cache bug that review had just fixed.

Read this at the start of every scheduled Bolt or Palette run. Learnings under
`.jules/bolt.md` / `.jules/palette.md` must not contradict it.

## 1. Check the open PR queue before you invent work

Before writing code or opening a pull request:

1. List open PRs: `gh pr list --state open --limit 50` (or the GitHub UI).
2. Match today’s brief against **title and branch** keywords (`Bolt`, `WorkUnit`,
   `inverted index`, `Palette`, `sources`, …).
3. Decide:

| Situation | What to do |
| --- | --- |
| Open PR already covers the same task | **Stop.** Do not open a new PR. Comment on the existing one only if you have a concrete, scoped improvement. |
| Same task merged to `main` recently | **Stop.** Only open a PR for a *new* defect not already fixed. |
| No matching open/recent PR | Proceed with **one** focused PR. |

Opening a duplicate PR for the same daily brief is waste: reviewers get a stack
of near-identical PRs, CI burns, and the maintainer triages by hand. Different
code for the same product outcome is still a duplicate PR.

## 2. Do not undo review fixes

If a commit on the branch (or a human reply in the PR) fixed a review finding:

- Do **not** reintroduce the old pattern in a later commit on the same PR.
- Do **not** delete regression tests that lock that fix.
- “Faster identity check” is not a reason to bypass content fingerprinting on
  mutable lists — match `core/domain.py` `_get_compiled_index`, and do not
  repeat the #386 identity-cache regression.

## 3. One PR per distinct outcome

One Jules run → at most one PR for that brief. Prefer pushing to the existing
open branch for the same brief over creating another `task/…-<random>` lane.

## 4. Learnings files

Append durable learnings to `.jules/bolt.md` / `.jules/palette.md` as usual.
If a learning contradicts §1–§2, **correct the learning** — do not teach the
unsafe shortcut again.
