# Standing instructions for Jules (Bolt / Palette)

**Audience:** Google Jules scheduled Bolt and Palette runs on this repo.  
**Why this exists:** Daily briefs reopened the same work as new PRs without
looking at the open queue (#374–#386 Bolt, #375–#387 Palette), and a post-review
commit on #386 reintroduced a cache bug that review had just fixed.

Read this at the start of every scheduled Bolt or Palette run. Learnings under
`.jules/bolt.md` / `.jules/palette.md` must not contradict it.

## 1. Check the open PR queue before you invent work

Before writing code or opening a pull request:

1. List open PRs for this repo (GitHub UI on the repo’s Pull requests tab, or
   any GitHub API / tool your session actually has — **do not assume `gh` is
   installed** in the Jules VM).
2. Match today’s brief against **title and branch** keywords (`Bolt`, `WorkUnit`,
   `inverted index`, `Palette`, `sources`, …).
3. Decide:

| Situation | What to do |
| --- | --- |
| Open PR already covers the same task | **Do not open a new PR.** Push fixes onto that branch if review asked for them; when threads are closed and CI is green, **finish it** (§5). |
| Same task merged to `main` recently | **Stop.** Only open a PR for a *new* defect not already fixed. |
| No matching open/recent PR | Proceed with **one** focused PR, then finish it through review → merge/hand-off (§5). |

Opening a duplicate PR for the same daily brief is waste: reviewers get a stack
of near-identical PRs, CI burns, and the maintainer triages by hand. Different
code for the same product outcome is still a duplicate PR.

## 2. Read what Qodo and CodeRabbit (“kanin”) already said

Review bots are part of the workflow in this repo. **Before** you write more
code, open another PR, or “optimize” an existing lane, you must read their
feedback on matching open PRs (and on the PR you are about to push to).

1. For each relevant open PR, open the conversation and **inline review threads**
   in the GitHub UI (or API if available).
2. Treat findings from **`qodo-code-review`** and **`coderabbitai`** as first-class:
   - Correctness / bug / major → fix on that PR (or explain why not), do not ignore.
   - Do not open a parallel PR that repeats the same bug the bots already flagged.
3. Scan PR conversation + Files changed review comments for those bot logins.
   Ignore the exact shell — what matters is reading the threads before writing more
   code.

4. If Qodo/CodeRabbit already named the issue (e.g. stale cache, wrong fingerprint),
   your next commit must address that thread — not reintroduce the old pattern under
   a “performance” commit message.

Skipping bot review is how #386 lost a fixed regression: identity-only cache came
back after CodeRabbit/Qodo had required content fingerprinting.

## 3. Do not undo review fixes

If a commit on the branch (or a human / bot reply in the PR) fixed a review finding:

- Do **not** reintroduce the old pattern in a later commit on the same PR.
- Do **not** delete regression tests that lock that fix.
- “Faster identity check” is not a reason to bypass content fingerprinting on
  mutable lists — match `core/domain.py` `_get_compiled_index`, and do not
  repeat the #386 identity-cache regression.

## 4. One PR per distinct outcome

One Jules run → at most one PR for that brief. Prefer pushing to the existing
open branch for the same brief over creating another `task/…-<random>` lane.

## 5. Finish the PR when review is done (especially Palette)

Closing the loop is part of the job. Leaving a finished Palette/Bolt PR open so
tomorrow’s brief opens a duplicate is how #375–#387 piled up.

**Jules sessions usually do not have the GitHub CLI (`gh`).** Do not depend on
`gh pr merge` / `gh pr list`. Use the GitHub UI (or any merge control your Jules
environment actually exposes). If you truly cannot merge, still **stop opening
duplicates** and hand off clearly (below).

**Ready to finish when all of these are true:**

1. **CI green** on the PR (or you just pushed a fix and CI is expected green).
2. **Qodo + CodeRabbit threads addressed** — each open thread either fixed in a
   commit (reply on the thread with what changed) or answered with a short
   “not applicable / why” note. Do not leave unanswered review comments.
3. **No unresolved human “please change X”** left in the thread.
4. **Branch is current enough** — update from `main` if the PR is behind, and
   never land a tip that deletes unrelated files that already exist on `main`
   (that is how #387 wiped liveness/bench/standing-instructions).

**Then, in order:**

1. **Merge if you can** — use the PR’s **Squash and merge** (preferred) in the
   GitHub UI / Jules merge affordance. Delete the branch when offered.
2. **If merge is blocked** (no permission, branch protection, required human
   review, conflict you cannot resolve): post one PR comment that the work is
   **ready to merge**, list what you fixed, and **stop**. Do **not** open a
   second PR for the same brief on the next run — pick up this PR instead.
3. Mark the PR **Ready for review** if it is still Draft.

**Do not merge / do not claim ready when:**

| Blocker | Action |
| --- | --- |
| Open review threads still unanswered | Fix or reply first (§2). |
| CI red | Fix, push, re-check. |
| PR touches report/invoice number engine, collectors billing math, or packaging/release files and a human asked to hold | Wait for maintainer. |
| Merge would drop files that exist on `main` but not on your tip | Sync from `main` first; do not force a stale tip through. |

“Comments addressed” means the conversation is closed out — not that you
opened another Palette PR with a slightly different styling pass.

## 6. Learnings files

Append durable learnings to `.jules/bolt.md` / `.jules/palette.md` as usual.
If a learning contradicts §1–§5, **correct the learning** — do not teach the
unsafe shortcut again.
