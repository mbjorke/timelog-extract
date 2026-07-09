# Session / chat title adapters (backlog id)

Status: active  
Last updated: 2026-07-09

When a pass tracks a GitHub board issue, the **conversation title** should carry
that id: `#342 · anchor-plan guardrail`. Prefer the **GitHub issue number**
(`#N`) over the story id (`GH-…`) when they differ — same rule as PR
`Closes` / `Part of` in `AGENTS.md`.

The shell **suggests** the title (`suggested_chat_title` in preflight /
`--chat-summary`). Each agent **applies** it with whatever its product supports.
Never block work if rename is unavailable.

Canonical loop note: [`rabbit-loop.md`](rabbit-loop.md) § Chat title.

## Format

```text
#<github-issue> · <≤6 word topic>
```

Source of the suggestion (in order):

1. Preflight `suggested_chat_title` / `--chat-summary` “Chat title (step 0a)”
2. Open PR title on the current branch that contains `#N`
3. Branch leaf that encodes an issue (`…-342`, `gh-342-…`)
4. Board card / issue the human named at the start of the pass

## Per-agent apply matrix

| Agent | How to apply (when possible) | Notes |
| --- | --- | --- |
| **Cursor** | MCP `rename_chat` (`cursor-app-control`) | Rule: `.cursor/rules/chat-title-backlog-id.mdc`; `/rabbit-loop` step 0a |
| **Claude Code** | Slash command `/rename #N · topic` | Also `claude -n '…'` at startup. Name shows in `/resume` + prompt bar |
| **Zed** (Agent Panel) | Click the thread title (or pencil) and set `#N · topic` | UI-only today — no agent API. Ask the human once if you cannot edit the title yourself |
| **Codex / Conductor / Antigravity / other ACP** | Use the product’s session/thread rename if it exists; else ask the human once | Prefer the same `#N · topic` string so handoffs stay searchable |
| **Headless / CI** | No-op | Suggestion still appears in preflight logs |

## Generator checklist (every agent)

At the start of a backlog-tied pass (rabbit-loop step **0a**, or picking up an
issue):

1. Read the suggested title from preflight / chat-summary when present.
2. Apply it with the row above for **this** agent.
3. If apply is impossible, print one line: `Chat title (manual): #N · topic` and continue.
4. Do **not** rename on every trivial turn; only when the tracked issue changes.

## Do not

- Put private customer names in the title
- Invent a fake `#N` when no issue exists yet (use `GH-…` from the task-prompt, or skip)
- Call Cursor MCP from non-Cursor agents
- Fail the loop because rename failed
