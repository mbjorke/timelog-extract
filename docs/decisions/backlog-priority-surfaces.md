# Decision: Backlog priority surfaces (labels are the claim, Project 3 is a view)

Status: Active — describes how the backlog actually works today
Date: 2026-07-25
Last updated: 2026-07-25
Owner: Maintainer + active agents

> **Scope note.** This doc records *where backlog priority lives* and *which
> surfaces an agent may read*. How priority is *decided* belongs to the
> product-owner pass (`docs/skills/gittan-product-owner.md`); how a loop hands
> work back to the maintainer belongs to `docs/skills/rabbit-loop.md`.

## Why

The backlog has two surfaces — `priority:*` labels on GitHub issues, and
the user-scoped GitHub Project board (called "Project 3" in local scripts;
exact URL lives in `scripts/rabbit_handoff.sh` defaults, not in committed docs)
— and they are not peers. Labels drive everything; the board is a human view
that is written to but never read back.

That asymmetry was implicit, so "how does the board add up?" kept being answered
against whichever surface the answerer could reach. Board drift is a recurring
finding in this repo for the same reason (`backlog-priority-2026-07-08-task.md`,
again in `backlog-priority-2026-07-25-task.md`, which had to set priority by
reading the code because the labels were not trusted as a view). Writing the
split down makes the next audit measure the right thing.

## The two surfaces

| Surface | Role | Who writes | Who reads |
|---|---|---|---|
| `priority:now` / `priority:next` / `priority:later` / `priority:do-not-build` labels | **Source of truth** for backlog position | the product-owner pass | every agent, every session, plain `repo` scope |
| Project 3 `Priority` / `Status` fields | Human view; ordered board for the maintainer | `scripts/rabbit_board_sync.sh`, `scripts/rabbit_handoff.sh` (needs `project` scope) | humans only |

`agent-ready` is an orthogonal label: it marks an issue whose product decision is
already made, so an implementer can start without asking a question. It does not
change band position.

## What actually reads and writes

Verified against the scripts, not the intent:

- **The product-owner pass sets labels.** `docs/skills/gittan-product-owner.md`
  already states labels are the source of truth and work with the plain `repo`
  scope.
- **Board writes are one-way.** `rabbit_board_sync.sh` puts the branch's PR on
  the board and sets a `Status`; `rabbit_handoff.sh` sets an issue to
  `Needs manual testing` and posts the checklist. Both need
  `gh auth refresh -s project`. `rabbit_loop.sh` stays read-only.
- **Nothing reads board `Status` back.** The kanin-loop preflight
  (`scripts/rabbit_workflow_context.sh`) contains no board or project query — it
  measures branch/remote distance only. No automation takes board `Status` as an
  input.

So board `Status` is an output. Treating it as an input is what produces the
drift the PO passes keep rediscovering.

## Why an agent session cannot read Project 3

This is a hard constraint, not a missing permission. Verified empirically on
2026-07-25 from a Claude Code web session, in this order:

1. **Projects v2 is GraphQL-only.** Projects Classic REST is sunset;
   `repos/{owner}/{repo}/projects` and `users/{login}/projects` both return
   `403`.
2. **GraphQL is pinned.** A `projectV2` query returns *"This GraphQL query is not
   enabled for this session — only the pinned set of PR-review operations is
   served."*
3. **The session is repo-scoped.** User-scoped paths return *"sessions are bound
   to their configured repositories. Use repository-scoped endpoints."* Project 3
   is a user-scoped object, outside that boundary.
4. **The web page carries no data.** The project view renders client-side; a
   fetch returns a JS shell with no items.
5. **Making the project public does not help.** It was tried. The wall is scope
   and transport, not visibility — and a public board can expose client names in
   item titles (cf. the docs-privacy backlog item on committed doc leaks), so the
   default should stay private.

Practical rule: **never ask for board access, a token, or a visibility change to
unblock a hosted agent session.** None of them work there. If such a session
genuinely needs board `Status`, a human pastes it, or a local `gh`-backed dump is
committed as a snapshot.

This is about hosted sessions only, and does **not** apply to a human on their own
machine. Board *writes* from a local `gh` do need the project scope —
`gh auth refresh -s project`, as `scripts/rabbit_board_sync.sh` and
`scripts/rabbit_handoff.sh` both report when it is missing. Skipping that refresh
is how board Status quietly stops being written at all.

## Rules that follow

- **Audit priority from labels + specs.** "What is in `now`?" means the
  `priority:now` label set, cross-read against each issue's spec Traceability.
- **A PO pass changes labels first.** Board fields are a follow-up mirror, best
  effort, and may lag without invalidating the pass.
- **Do not cite board `Status` as evidence** in a spec, PR, or review — it is not
  reachable by whoever reads your claim later. Cite the label and the code.
- **Answer scope honestly.** If asked how the board looks and you can only see
  labels, say which surface you measured before reporting numbers.

## Open tension: agent↔task ownership

The agent-ownership backlog item proposes board `Status` as the ownership claim
("the board Status *is* the claim") so the kanin-loop preflight can refuse a task
another agent owns. That slice is **not built**, and as specified it would place
the claim on the one surface no agent can read.

If that item is picked up, the claim needs a machine-readable home — a `status:*`
label alongside `priority:*` is the cheap version, since labels already work for
every agent with the scope they already have. The board can keep mirroring it for
the maintainer's eye.

## References

- `docs/skills/gittan-product-owner.md` — the prioritization pass (labels).
- `docs/skills/rabbit-loop.md`, `AGENTS.md` § *Kanin-loop* — board handoff writes.
- `docs/task-prompts/backlog-priority-2026-07-25-task.md` — the pass that
  re-confirmed board drift and re-scoped the board-sync follow-up.
- `docs/ideas/kanin-handoff-board-closeout.md` — agent↔task ownership; the open
  tension above.
- Docs-privacy backlog item — pre-existing client-name leaks in committed docs;
  why a public board is not a safe workaround.
