# Effective human → agent “commands” (inspiration)

*This is not repository policy — for that, read [`AGENTS.md`](../../AGENTS.md). This file collects **patterns and links** that reduce ambiguity and “wrong but confident” work when humans steer coding agents, without inventing new internal abbreviations.*

## What works across codebases (common thread)

1. **Constraints before cleverness** — state *what not to do*, in-repo paths to follow, and the **test/CI gate** before the agent “optimises.” Many teams mirror this in checked-in rules (`.cursor/rules/`, `AGENTS.md`, Copilot / Codex instruction files) so the model is not inferring from chat alone.
2. **One clear intent per turn** (or a short *numbered* batch). Large blob prompts with mixed refactor + feature + docs tend to be executed in the wrong order.
3. **Success criteria the agent can check** — e.g. “`./scripts/run_autotests.sh` green”, “no new lints in touched files”, “user-visible string in English in PR” — not “make it good.”
4. **Store context in the repo, not in the window** — specs, task prompts, and small “TIL / lexicon” notes (see [`docs/ideas/team-lexicon.md`](../ideas/team-lexicon.md)) so the *next* session and other machines get the same contract. Anthropic and others call this *context* or *memory* **engineering**, not a longer chat line.
5. **Specify → plan → implement → verify** (lightweight SDD) — for non-trivial work, many workflows ask the agent to *read* the spec, produce a *short plan* or file list, *then* edit. Skipping the plan step often increases diff size and reverts.
6. **Encourage “repair”** — if output is off, a follow-up that names *one* issue (“tests fail in `X` for reason `Y`; fix that only”) beats a second mega-prompt.

## Vague phrasing → stronger phrasing (examples)

| Vague (high misinterpretation risk) | More effective (same intent) |
| ---------------------------------- | ----------------------------- |
| “Clean this up” | “Refactor *only* `path/to.py`; behaviour unchanged; run `.../run_autotests.sh`.” |
| “Max five tasks in one commit” (parsed as a hard *policy* number) | “Break into a **checklist** of 3–7 *related* sub-steps; one **intent** per commit; stop if scope widens.” |
| “It should be fast / secure / nice” | “**Acceptance:** … ; **out of scope:** … ; **measure** or **static check** to run: …” |
| “Use best practices” | “Follow [`AGENTS.md`](../../AGENTS.md) and existing patterns in `neighbour_module/` — copy structure, not invent a new one.” |
| “Merge dev and main” (underspecified risk) | Use a **runbook** and fixed git/GitHub steps — e.g. [`docs/runbooks/dev-main-alignment.md`](../runbooks/dev-main-alignment.md) — including tag backup and *no* force to `main`. |
| “Refactor the whole module” (no sense of size) | Think **blast radius** (how many files / subsystems). If impact is unclear, ask the agent to **propose a few options** *before* editing; prefer **atomic commits** so you can reset one change. |

## Peter Steinberger (steipete) — what fits here, what does *not* replace `AGENTS.md`

Peter Steinberger ([steipete](https://steipete.me/)) writes from **solo, very high-velocity *agentic* work** (many parallel agent sessions, heavy use of a specific harness + model). Two posts that sum up the style: *Just Talk To It* — <https://steipete.me/posts/just-talk-to-it> — and *My Current AI Dev Workflow* — <https://steipete.me/posts/2025/optimal-ai-development-workflow>.

**Ideas that align with this repo (worth stealing):**

- **Blast radius** — before a change, how big is the footprint? If several “large” changes at once, isolated commits and rollback get hard; prefer many small, coherent edits (same idea as one intent per turn).
- **Interrupt without shame** — stop a runaway session; ask for a **status**; then continue, course-correct, or abort. Reduces “confidently wrong” long runs.
- **“Give me options before making changes”** when you are uncertain — maps to *clarify impact first*, not only to our spec-first habit.
- **Atomic commits** by the agent, with a **tight “agent file”** (he iterates a personal instruction file; we use [`AGENTS.md`](../../AGENTS.md) + task prompts in-repo for the *next* human/agent).
- **Shorter chat prompts** when the **tool + model** read the tree well and push back on silly requests — *in that setup*, long spec charades are less necessary for *local* work.

**Where it can *look* in tension (but is really a different context):**

- He explicitly finds **plan mode and “rigorous structure docs”** in the harness a **workaround** *when* the model is over-eager. This repository is **open**, **branch-protected**, and used by **multiple** people and **cloud** agents: **checked-in** rules, runbooks, and PR English are not optional politeness — they are how we keep *shared* `main` safe. So: **conversational “just talk to it”** and **durable `docs/*` contracts** are complementary — use chat when you are the only operator; use files when the work must **survive the next session and another machine**.
- **Parallel agents in the same working tree** works for *his* stack and muscle memory; our [`AGENTS.md`](../../AGENTS.md) still prefers **worktrees** or narrow branches when two scopes would fight over the same files — *not* because Steinberger is “wrong,” but because merge conflicts and CI noise scale with blast radius in a multi-PR world.

**Net:** import **blast radius**, **interrupt + status**, **options-first**, and **atomic commits** into how you *phrase* work; keep **runbooks, `AGENTS.md`, and handoff prompts** as the *shared* safety layer for this project.

## Ecosystem links (stables you can re-read; URLs may move)

- **Anthropic — context engineering for agents** — *Effective context engineering for AI agents* (engineering blog): <https://www.anthropic.com/engineering/effective-context-engineering-for-agents> — treats durable context in files and tool boundaries, not one-off prompts.
- **Anthropic — prompt engineering (Claude)** — <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices> — clarity, directness, examples, and structured sections (e.g. XML-style blocks for *instructions* vs *examples* vs *input* in complex prompts).
- **Addy Osmani — “How to write a good spec for AI agents”** — (Elevate / Substack) — scoping, acceptance, and *when* to ask the model to elicit requirements before implementation.
- **arXiv — *Ten simple rules for AI-assisted coding in science* (Lozano, 2025, life-science slant, rules apply broadly) — <https://arxiv.org/html/2510.22254> — human verification, test discipline, and explicit scope.
- **Peter Steinberger** — *Just talk to it* / *optimal AI workflow* (see section above) — high-throughput **solo** agentic patterns: blast radius, short prompts *when* the harness fits, pushback on over-structured “charades” *for that* workflow; **not** a substitute for team runbooks in an open repo.

## In *this* repo, prefer these levers

| Lever | Where |
| ----- | ----- |
| **Hard rules (tests, branches, privacy)** | [`AGENTS.md`](../../AGENTS.md) |
| **Implementation checklist for a feature** | [`docs/task-prompts/`](../task-prompts/) |
| **Steady “how we say it” in chat** (short Swedish OK) | [`docs/ideas/team-lexicon.md`](../ideas/team-lexicon.md) |
| **Durable learnings from the maintainer** | [`docs/ideas/til/`](../ideas/til/) |
| **Orch / GitHub operations with handoff to another agent** | [`docs/task-prompts/dev-main-alignment-handoff.md`](../task-prompts/dev-main-alignment-handoff.md) and related runbooks |

*Bottom line: **full words and explicit acceptance** beat mystery abbreviations in anything that leaves the org. In **solo** sessions, a short natural-language prompt is fine when the tool reads the repo well; in **shared** work, the **checked-in** contract still wins. Use the [team lexicon](../ideas/team-lexicon.md) only for stable, agreed in-team shorthand.*
