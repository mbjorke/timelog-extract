# Shared rules — every Jules persona

Status: active
Last updated: 2026-08-04

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
Pull requests in this repo — from Jules, Cursor and Claude alike — are all
authored by `mbjorke`, so you cannot reliably tell whose work you are touching.
Leave other branches alone.
