# Jules persona prompts

Status: **retired — schedules deleted and repository access revoked 2026-08-06**
Last updated: 2026-08-06

## What happened

Three scheduled Jules personas (Bolt ⚡, Palette 🎨, Sentinel 🛡️) ran daily
against this repo through July and early August 2026. They produced 29 open PRs
in ten days, 14 of them duplicates of each other — including the same
`briox_connection_test.py` HTTPS hardening written **eight** separate times
(#481, #484, #487, #493, #496, #500, #503, #511).

The root cause was not a bad prompt. The prompts had never existed in this repo
at all: `git log --all -S'security-focused'` returns zero hits across the full
history. Each persona's instructions lived only in the Jules web UI, so nothing
that shaped agent behaviour was reviewable, diffable, or improvable here. The
repo held the *rules* (`../jules-standing-instructions.md`) and the *journals*
the agents appended to (`.jules/*.md`) — but never the instructions themselves.
The rules said "check the open PR queue first"; the prompts never did.

Deleting the schedules turned out not to be enough. The agents also reacted to
**events** — a new review comment, a new commit — independently of any schedule.
Five times in one day a Jules commit landed 2–14 minutes after one of mine, at
five different hours with no relation to the configured 04:00 / 22:00 / 23:30
runs. Four of those five rewrote the fix they had just agreed with in the review
thread; three deleted regression tests in the process, one of them three times
on the same PR (#499).

Repository access was revoked on 2026-08-06. These files are kept as the record,
and because the rules in them are worth reusing.

## What is still live

**`scripts/rabbit_loop.sh --agent-gate`** is the only part of this that runs. It
resolves the PR head, verifies it matches local `HEAD`, and blocks when
`base..HEAD` carries more than one distinct commit author, or an author other
than the expected one. It is deliberately *not* wired into `--merge-gate` or
`--classify-merge` — a separate opt-in check, so it cannot silently change when
existing merges are allowed.

It applies to any agent, not only Jules. Note what it cannot do: it gates the
**merge**, not the push. Nothing here would have prevented the rewrites above.

**`shared-rules.md`** is agent-agnostic and the useful part of this directory.
If a scheduled agent is ever set up again — Jules or otherwise — start there
rather than from a blank prompt. The rules that matter fail closed: a run that
cannot list the open PRs ends without opening one, and that counts as a
*successful* run.

## Files

| File | What it is |
| --- | --- |
| [`shared-rules.md`](shared-rules.md) | Blocking pre-work checks, and the anti-patterns learned the hard way. Reusable for any agent. |
| [`sentinel.md`](sentinel.md) | 🛡️ Security — credentials, transport, secret leakage |
| [`bolt.md`](bolt.md) | ⚡ Performance — hot paths in collectors and core |
| [`palette.md`](palette.md) | 🎨 CLI UX — terminal output and interactive flows |

Related: [`../jules-standing-instructions.md`](../jules-standing-instructions.md)
(the longer rationale), [`../jules-finisher-agents.md`](../jules-finisher-agents.md)
(merge gate — read its author-gate warning before re-enabling anything).

## If a scheduled agent is ever set up again

Keep the scheduled prompt **thin** — a pointer, not the content — so behaviour
changes by editing a reviewed file rather than a web form:

```
Du är "Sentinel". Läs docs/contributing/jules-personas/sentinel.md i
mbjorke/timelog-extract och följ den. Följ även shared-rules.md som den
hänvisar till. Om du inte kan läsa filerna: avsluta utan att öppna någon PR.
```

Two things this round proved, both worth deciding before the first run:

- **Cap the output, not only the behaviour.** These agents produced roughly
  three PRs a day and did not self-limit. An unattended week is an unattended
  backlog, and triaging a duplicate costs more than writing the original did.
- **Assume event-driven runs, not only scheduled ones.** Pausing a schedule does
  not stop an agent that reacts to review comments. If it needs to stop, revoke
  repository access.
