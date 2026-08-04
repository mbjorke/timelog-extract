# Jules persona prompts

Status: active
Last updated: 2026-08-04

## Why this directory exists

The Bolt / Palette / Sentinel persona prompts used to live **only** in the Jules
web UI (jules.google.com → Scheduled). Nothing that shaped agent behaviour was
under version control, reviewable, or diffable — the repo held only the *rules*
(`../jules-standing-instructions.md`) and the *journals* the agents append to
(`.jules/*.md`).

That gap is how #478–#506 happened: 29 open PRs in ten days, 14 of them
duplicates of each other, including the same `briox_connection_test.py` HTTPS
fix written seven separate times. The rules said "check the open PR queue
first"; the prompts never did.

## How this works

Keep the scheduled prompt in Jules **thin** — a pointer, not the content:

```
Du är "Sentinel". Läs docs/contributing/jules-personas/sentinel.md i
mbjorke/timelog-extract och följ den. Följ även shared-rules.md som den
hänvisar till. Om du inte kan läsa filerna: avsluta utan att öppna någon PR.
```

Behaviour then changes by editing a file in this repo — reviewable in a PR,
visible in `git log`, and impossible to drift silently between the three
personas.

## Files

| File | What it is |
| --- | --- |
| [`shared-rules.md`](shared-rules.md) | Blocking pre-work checks. Identical for every persona. |
| [`sentinel.md`](sentinel.md) | 🛡️ Security — credentials, transport, secret leakage |
| [`bolt.md`](bolt.md) | ⚡ Performance — hot paths in collectors and core |
| [`palette.md`](palette.md) | 🎨 CLI UX — terminal output and interactive flows |

Related: [`../jules-standing-instructions.md`](../jules-standing-instructions.md)
(the longer rationale), [`../jules-finisher-agents.md`](../jules-finisher-agents.md)
(merge gate — see its author-gate warning before re-enabling anything).

## Schedule

As configured in the Jules UI (times in GMT+3):

| Persona | Runs | UTC |
| --- | --- | --- |
| Sentinel | Daily 04:00 | 01:00 |
| Bolt | Daily 22:00 | 19:00 |
| Palette | Daily 23:30 | 20:30 |

Pause all three in the Jules UI whenever nobody is available to triage. These
agents produce roughly three PRs a day and do not self-limit; an unattended
week is an unattended backlog.
