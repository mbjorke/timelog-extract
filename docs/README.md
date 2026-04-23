# Documentation index

This folder is the **single map** for where to put and find docs. Prefer this file when routing new material; keep it updated when you add top-level categories.

**How product docs relate (precedence, manifesto vs depth):** [`product/vision-documents.md`](product/vision-documents.md) — read this before large edits to vision, scope, or public copy.

For **code and script layout** (not doc taxonomy), see [`meta/structure.md`](meta/structure.md).

**Sensitive business data** (revenue, detailed metrics, unpublished numbers): keep under **gitignored `private/`** — see [`meta/private-local-notes.md`](meta/private-local-notes.md).

## Top-level categories

| Path | Purpose |
| ---- | ------- |
| `decisions/` | Stable policy and architecture decisions (how we work, gates, routines). |
| `specs/` | Active implementation specs: goals, non-goals, acceptance criteria, test plan. |
| `task-prompts/` | Execution prompts and checklists for implementation and validation tasks. |
| `runbooks/` | Operational how-tos: CI, versioning, release checklists, manual QA matrices. Optional dev-only tooling (e.g. [optional-caveman-agent-setup.md](runbooks/optional-caveman-agent-setup.md)) lives here too. |
| `product/` | Vision, scope, strategy, north-star metrics, accuracy plans. |
| `roadmaps/` | Time-phased goals across horizons (near-term and long-term); plural because multiple documents or themes are expected. See [`roadmaps/README.md`](roadmaps/README.md). |
| `business/` | Sponsorship, positioning, channel copy drafts (non-binding unless stated). |
| `security/` | Privacy baseline, license intent, upstream risk notes. |
| `sources/` | Collectors, flags, and integration notes (including backlog integrations). |
| `ideas/` | Exploratory proposals and learning notes — not final policy. **Maintainer TIL (human → agent) by month:** [`ideas/til/`](ideas/til/). |
| `contributing/` | Contributor-focused guides (e.g. [ai-assisted-work.md](contributing/ai-assisted-work.md), [agent-task-handover-prompt.md](contributing/agent-task-handover-prompt.md)). |
| `meta/` | Repo layout ([`structure.md`](meta/structure.md)), private-business policy ([`private-local-notes.md`](meta/private-local-notes.md)), and [`documentation-structure.md`](meta/documentation-structure.md) redirect. |
| `inspiration/` | Short external links and patterns before they become specs; see [`inspiration/README.md`](inspiration/README.md). |
| `incidents/` | Postmortems and corrective actions after concrete incidents. |
| `legacy/` | Old docs kept for reference only — **not** maintained like active docs; not a curated “museum,” just stuff we do not delete yet. |
| `brand/` | Brand assets, visual identity ([`identity.md`](brand/identity.md)), and team/product [`values.md`](brand/values.md). |
| `evals/` | Golden eval and similar evaluation artifacts. |
| `live-terminal-sandbox/` | Build tracking for the public live-terminal demo. |
| `marketing/` | Marketing drafts (e.g. [DAIS Substack long-form](marketing/dais-substack-article-gittan-origin.md)). |

## Quick routing

- **Defines a current rule** → `decisions/`
- **Approved work to build** → `specs/`
- **Triage onboarding timestamp spike spec (S1)** → [`specs/triage-onboarding-timestamp-spike-spec.md`](specs/triage-onboarding-timestamp-spike-spec.md)
- **Implementation checklist / agent prompt** → `task-prompts/`
- **Apr 29 live demo — CLI polish backlog (current focus)** → [`runbooks/cli-polish-backlog-for-apr29.md`](runbooks/cli-polish-backlog-for-apr29.md)
- **How to run CI, release, or QA** → `runbooks/` (optional **Homebrew tap** sketch for `brew install gittan`: [`runbooks/homebrew-tap.md`](runbooks/homebrew-tap.md))
- **Separate `dev` vs `main` (forks / second integration branch — safe alignment, tags, handoff)** → [`runbooks/dev-main-alignment.md`](runbooks/dev-main-alignment.md) + prompt [`task-prompts/dev-main-alignment-handoff.md`](task-prompts/dev-main-alignment-handoff.md) — default upstream flow is `task/* → main` ([`BRANCH.md`](../BRANCH.md))
- **What Gittan is and should ship** → `product/` — start with [`product/vision-documents.md`](product/vision-documents.md) for hierarchy
- **Values, culture, what we won’t do (public / contributors)** → [`brand/values.md`](brand/values.md)
- **TIL the maintainer taught the agent (by month, short bullets)** → [`ideas/til/`](ideas/til/) (see `AGENTS.md` → *Maintainer TIL*)
- **Phrasing work for agents (external patterns, reduce misreads)** → [`inspiration/effective-commands-for-agents.md`](inspiration/effective-commands-for-agents.md)
- **Committed timeline / milestones (short or long horizon)** → `roadmaps/`
- **Fundraising / positioning copy** → `business/`
- **Privacy and licensing posture** → `security/`
- **How data enters the tool** → `sources/`
- **Exploratory only, team-lexicon (människa–agent, inkl. TIL)** → `ideas/` (t.ex. [`ideas/team-lexicon.md`](ideas/team-lexicon.md))
- **Current triage onboarding spike (top-sites + timestamp)** → [`ideas/triage-onboarding-spike-2026-04.md`](ideas/triage-onboarding-spike-2026-04.md)
- **No longer current but you still want the file in-repo** → `legacy/`

## Naming

- Prefer **kebab-case** file names.
- Keep tooling-standard root filenames (`README.md`, `CHANGELOG.md`, `AGENTS.md`, etc.) unchanged at repo root.

## Code and CLI

User-facing strings in the codebase should **not** embed `docs/legacy/` paths. Use `runbooks/`, `decisions/`, `specs/`, or `product/` instead; link to `legacy/` only from prose docs when history matters. See `AGENTS.md` → *Documentation paths in code*.

## Legacy pointer

Older references to `docs/documentation-structure.md` still resolve via [`meta/documentation-structure.md`](meta/documentation-structure.md); that file redirects here.

Only **`README.md`** should live at the `docs/` root; everything else belongs in a subfolder.
