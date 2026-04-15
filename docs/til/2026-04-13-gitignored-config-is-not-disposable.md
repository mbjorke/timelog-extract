# TIL: Gitignored config is not disposable

**Date:** 2026-04-13  
**Area:** Orchestration — data safety  
**Agent:** Cursor (manual matrix scenario testing)

## What happened

During scenario testing, an agent moved `timelog_projects.json` to a `.bak` filename
as a temporary step. The file was never restored. Because it is gitignored, there was
no staged change, no diff, no warning — it just silently disappeared from the working
tree.

Project classification dropped to fallback/minimal quality. The user noticed gaps in
time reporting before diagnosing the cause. Recovery required locating
`timelog_projects.json.bak` in git history and manually restoring it.

## The lesson

**Gitignored means not tracked, not not important.** An agent that sees a gitignored
file may treat it as ephemeral — scratch state that can be moved, renamed, or deleted
freely. That assumption is wrong for `timelog_projects.json`, which is the primary
user configuration and has no automated recovery path.

The broader pattern: files that are gitignored *because they contain private or
user-specific data* are often the most critical files in the repo. The gitignore entry
is a privacy/policy boundary, not a signal that the file is disposable.

A second pattern: **testing is a high-risk moment for data loss.** "I'll just move it
aside for the test" is a common path to accidental deletion, especially across
worktree switches or branch checkouts where the original location is no longer obvious.

## What changed

- `AGENTS.md` — **Do not #7** in the top-level prohibition table; "Local data safety"
  section already covers this with a reference to this incident.
- Setup (0.2.2): timestamped backups before recreating malformed config files;
  regression tests for valid-config keep and malformed-config backup/recreate.

## Orchestration pattern

> Treat any gitignored file that contains user data or project config as **critical**.
> Before moving, renaming, or deleting it, either confirm with the user or copy it to
> a timestamped path outside the repo first.
>
> During scenario testing, never use the live config as a test fixture. Copy it, test
> against the copy, restore before finishing.
