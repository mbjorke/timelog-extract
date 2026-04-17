# AI-assisted contribution (all tools)

This project is edited with many clients: **Claude Code**, **Codex**, **Cursor**, **Slay**, **VS Code**, **Zed**, **Lovable**, and plain terminal. Tooling changes often; **repo-owned markdown** stays the stable contract.

## Single source of truth (do not fork policy in your head)

| Priority | File | Role |
| -------- | ---- | ---- |
| 1 | [`AGENTS.md`](../../AGENTS.md) | **Canonical** rules for agents and automation: branches, safety, timelog, PR language, tests before push. |
| 2 | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) | Human contributor entry: PR flow, setup, style. |
| 3 | [`docs/README.md`](../README.md) | Where documentation *files* live (taxonomy). |
| 4 | [`BRANCH.md`](../../BRANCH.md), [`docs/runbooks/ci.md`](../runbooks/ci.md) | Branch and CI mechanics. |

If a tool-specific file (e.g. `CLAUDE.md`) disagrees with `AGENTS.md`, **`AGENTS.md` wins.**

## Thin tool entry points (optional)

Keep these **short**: duplicate only orientation, not policy.

| Tool / context | Practical entry |
| -------------- | ---------------- |
| **Claude Code** | [`CLAUDE.md`](../../CLAUDE.md) → points at `AGENTS.md`. |
| **Cursor** | [`.cursor/rules/`](../../.cursor/rules/) for workspace rules; still read `AGENTS.md`. |
| **Codex / ChatGPT / other chat UIs** | Paste or attach **`AGENTS.md`** (and `CONTRIBUTING.md` for first PR). No separate file required unless we add a one-line stub later. |
| **VS Code / Zed (no agent)** | Open `AGENTS.md` + `CONTRIBUTING.md` in editor; same content. |
| **Slay-zone** | Use whatever “project context” feature exists; **point it at `AGENTS.md`**. |
| **Lovable / web IDEs** | Not authoritative for this repo’s CLI; use for experiments only. Copy **decisions back** into `docs/decisions/` or `docs/specs/` if they should stick. |

Adding a new vendor-specific file (e.g. `GEMINI.md`) is OK **only** if it is a stub: “Read `AGENTS.md` first” + link to architecture in `CLAUDE.md` or `README.md`.

## Skills vs rules vs long docs

- **Cursor Rules** (`.cursor/rules/*.mdc`): good for **always-on** repo constraints (e.g. pre-push gate). Checked into git; all contributors get them in Cursor.
- **Cursor / Claude Skills** (`SKILL.md`, user-level dirs): good for **personal** workflow (tone, formatting). Prefer **not** to commit heavy skills until the ecosystem stabilizes; document optional patterns in [`../runbooks/optional-caveman-agent-setup.md`](../runbooks/optional-caveman-agent-setup.md) instead of mandating one skill.
- **`AGENTS.md`**: long but **one place** — better than five half-copies.

If we later add a **repo-level** `SKILL.md`, it should be a **thin** pointer to `AGENTS.md` + test command, not a second policy document.

## Faster onboarding checklist (any tool)

1. Read **`AGENTS.md`** (at least: branch policy, git safety, test gate).
2. Read **`CONTRIBUTING.md`** (PR language English, `task/*` branch).
3. Run **`bash scripts/run_autotests.sh`** before pushing.
4. Feature work: skim **`CLAUDE.md`** architecture section *or* root **`README.md`** “Architecture” — same facts, pick one.

## Where “inspiration” lives

Product bets and GTM thinking stay in **`docs/ideas/`** (e.g. `opportunities.md`).  
**Ad-hoc links, patterns, and “we saw this elsewhere”** notes belong in **`docs/inspiration/`** — see [`../inspiration/README.md`](../inspiration/README.md).  
Formal direction still moves to **`docs/decisions/`** or **`docs/specs/`** when we commit to it.
