# Decision: Agent review contract (CodeRabbit signal → human or Cursor execution)

Status: Draft (process template); **Gittan bounds below are active for this repo**  
Date: 2026-04-18  
Last updated: 2026-04-18 (Copilot CLI remote section)  
Owner: Maintainer + active agents

## Why

Automated review (often **CodeRabbit** in this repo) produces **findings**; **execution** (fixes) may be done by a **human** or by a **Cursor agent** (or another coding agent). Those are different systems: there is **no** guaranteed machine-to-machine contract between “review bot” and “IDE agent” unless we **define one in the repo** and follow it manually or via vendor features.

This document sketches a **pre-agreed contract** so that:

- **High-severity** items get **explicit** handling expectations.
- **Executors** know what they may change **without** a new product decision.
- **Review threads** stay the source of truth for *what* was wrong; this doc defines *how* we respond by severity.

## Roles

| Role | Typical tool | Responsibility |
|------|----------------|----------------|
| **Reviewer / signal** | CodeRabbit (GitHub app or `coderabbit` CLI) | Flag issues, severity, concrete suggestions. Does not replace maintainer judgment. |
| **Executor** | Human, or Cursor Cloud / IDE agent | Implement fixes **within the contract**; push commits; reply in thread with SHA. |
| **Gate** | Maintainer | Approves anything outside the contract or that touches security, licensing, or release semantics. |

## Severity → allowed response (contract)

Adjust labels to match your tracker; default mapping:

| Severity | Meaning (examples) | Executor **may** do without extra approval | **Always** escalate |
|----------|---------------------|---------------------------------------------|----------------------|
| **Critical** | Secret exposure, auth bypass, data loss risk | **Nothing automatic.** Open a focused fix or revert; page maintainer if needed. | Dependency with legal review, production creds |
| **High** | CI broken, test wrong, clear bug with bounded patch | Fix **only** the cited files/lines; add/adjust tests proving the fix; one logical commit per batch. | API/behavior change affecting users without spec |
| **Medium** | Style, maintainability, missing edge-case test | Same as high if change is **≤ 5 tracked files** in this repo (see below) and `./scripts/run_autotests.sh` passes. | Refactors that broaden scope |
| **Low** | Nit, doc typo, optional cleanup | Batch in a single “chore” commit if desired; or defer. | — |

### Gittan / `timelog-extract` — concrete bounds

**`N` files (medium):** at most **5** tracked files touched in a single response batch (not counting generated noise). If CodeRabbit spans more, split commits or defer part.

**Usually safe for executor (high/medium)** — fix review findings here when the finding explicitly points at these areas:

- `core/`, `collectors/`, `outputs/`, `tests/`, `scripts/` (scripts that only read repo state; no destructive defaults).
- `docs/` including `docs/runbooks/`, `docs/decisions/`, `docs/product/`, `docs/specs/`.
- `.cursor/rules/` for rule text aligned with existing `AGENTS.md` / style guides.
- Refactors **only** to satisfy the **500-line policy** for tracked Python (split/move) when the review or CI requires it.

**Needs explicit maintainer nod or dedicated PR description** (do **not** do as a silent drive-by):

- **`pyproject.toml`** — dependencies, `requires-python`, classifiers, version string.
- **`LICENSE`**, copyright headers, SPDX, or **license classifiers** that affect distribution.
- **Versioned release artifacts** — `CHANGELOG.md` section for a **numbered release**, `pyproject` version bump, git tags (release workflow).
- **`.github/workflows/`** — anything that changes **secrets**, **deploy keys**, **trusted publishing**, or **CI security posture**.
- **`private/`** — do not stage or commit (gitignored); never paste real user paths into committed docs.
- **`timelog_projects.json` at repo root** — treat as **user data** if present locally; **tests** may use fixtures under `tests/` only. Do not ship schema changes without a spec/decision note.

**Critical / security findings:** same as global table — **no** autonomous dependency or secret changes; maintainer reviews before merge.

**Verification before push:** `./scripts/run_autotests.sh` (and `bash scripts/cli_impact_smoke.sh` for CLI-facing edits per `AGENTS.md`).

## Hand-off protocol (practical)

1. **Reviewer** leaves findings on the PR (or CLI output before push).
2. **Executor** addresses **high** first (or critical first), within the table above.
3. Reply in thread: `Addressed in <short-sha>: <one line>` then resolve when CI is green.
4. If a finding is **out of contract** (e.g. “large refactor”), reply: **Deferred: reason** and link an issue or decision doc.

This is the closest we get to a “pre-agreed contract” until vendors offer a **single** negotiated channel between review bots and IDE agents.

## CodeRabbit: cloud features that relate to “rabbit asks, agent fixes”

Product names and availability change — use **[CodeRabbit documentation](https://docs.coderabbit.ai/)** and **[changelog](https://docs.coderabbit.ai/changelog)** as source of truth. As of common 2025–2026 messaging, items in this family include:

- **Autofix / automated fixes** — applies certain fixes on the PR branch (scope and safety rules are product-defined; not the same as Cursor).
- **Fix-all / batched remediation** — aggregates findings so one can drive a **single** agent session or pass (see also their blog on *fixing issues with AI agents*).
- **Pipeline remediation** — CI failure diagnosis/fix flows for common CI systems.
- **CodeRabbit Skills** — integrations so **Skills-compatible agents** can trigger reviews from natural language (still **not** a bilateral Cursor ↔ CodeRabbit negotiation in one thread).
- **CLI** (`coderabbit review`) — local review without consuming GitHub **hourly** review quota the same way; see `AGENTS.md`.

**Interpretation:** CodeRabbit has been **shipping** cloud-side automation that **narrows the gap** between “findings” and “applied fixes,” but **your** contract (this doc + `AGENTS.md`) still defines **what** a Cursor agent may do **in this repository**.

## GitHub Copilot CLI: remote access (`copilot --remote`)

GitHub ships **remote control of Copilot CLI sessions** from the browser or GitHub Mobile (public preview as of [April 2026 changelog](https://github.blog/changelog/2026-04-13-remote-control-cli-sessions-on-web-and-mobile-in-public-preview/)): start a session with **`copilot --remote`** (or enable **`/remote`** inside a session). This is a **first-party** bridge between a **local CLI** in a repo on GitHub.com and a **web UI** — different from Cursor, but relevant to “cloud + agent + terminal” orchestration.

- **How-to:** [Steering a GitHub Copilot CLI session from another device](https://docs.github.com/en/copilot/how-tos/copilot-cli/steer-remotely)
- **Concept:** [About remote access to GitHub Copilot CLI sessions](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-remote-access)

**This repository:** GitHub’s **Agents** view for the repo (e.g. `https://github.com/mbjorke/timelog-extract/agents`) lists Copilot-related agent activity **on GitHub**; it does **not** replace this doc’s rules for **who may change what** on the branch — still use PRs and the contract above.

**Relation to CodeRabbit:** still separate products; remote Copilot CLI does **not** auto-sync with CodeRabbit findings unless **you** connect the workflow (e.g. review in PR → prompt Copilot CLI session with scope).

## Relation to Cursor

- **Cursor agents** do not receive a formal API callback from CodeRabbit when severity = high.
- Practical pattern: **export** findings (PR tab, or paste CLI summary) → **prompt Cursor** (or a **Copilot CLI** session, including remote-steered) with: “Fix only HIGH items in scope X per `docs/decisions/agent-review-contract.md`.”
- If GitHub/Cursor later adds **@mentions** or **agent triggers** on PRs, revisit this doc and add a subsection.

## Links

- Review cadence and rate limits: [`AGENTS.md`](../../AGENTS.md) → *Review Cadence (CodeRabbit)*.
- Task handover prompt: [`docs/contributing/agent-task-handover-prompt.md`](../contributing/agent-task-handover-prompt.md).
