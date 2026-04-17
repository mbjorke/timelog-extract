# Documentation index

This folder is the **single map** for where to put and find docs. Prefer this file when routing new material; keep it updated when you add top-level categories.

For **code and script layout** (not doc taxonomy), see [`structure.md`](structure.md).

## Top-level categories

| Path | Purpose |
| ---- | ------- |
| `decisions/` | Stable policy and architecture decisions (how we work, gates, routines). |
| `specs/` | Active implementation specs: goals, non-goals, acceptance criteria, test plan. |
| `task-prompts/` | Execution prompts and checklists for implementation and validation tasks. |
| `runbooks/` | Operational how-tos: CI, versioning, release checklists, manual QA matrices. |
| `product/` | Vision, scope, strategy, north-star metrics, accuracy plans. |
| `roadmaps/` | Time-phased goals across horizons (near-term and long-term); plural because multiple documents or themes are expected. See [`roadmaps/README.md`](roadmaps/README.md). |
| `business/` | Sponsorship, positioning, channel copy drafts (non-binding unless stated). |
| `security/` | Privacy baseline, license intent, upstream risk notes. |
| `sources/` | Collectors, flags, and integration notes (including backlog integrations). |
| `ideas/` | Exploratory proposals and learning notes — not final policy. |
| `incidents/` | Postmortems and corrective actions after concrete incidents. |
| `legacy/` | Old docs kept for reference only — **not** maintained like active docs; not a curated “museum,” just stuff we do not delete yet. |
| `brand/` | Brand assets and identity notes. |
| `evals/` | Golden eval and similar evaluation artifacts. |
| `live-terminal-sandbox/` | Build tracking for the public live-terminal demo. |
| `marketing/` | Marketing drafts. |

## Quick routing

- **Defines a current rule** → `decisions/`
- **Approved work to build** → `specs/`
- **Implementation checklist / agent prompt** → `task-prompts/`
- **How to run CI, release, or QA** → `runbooks/`
- **What Gittan is and should ship** → `product/`
- **Committed timeline / milestones (short or long horizon)** → `roadmaps/`
- **Fundraising / positioning copy** → `business/`
- **Privacy and licensing posture** → `security/`
- **How data enters the tool** → `sources/`
- **Exploratory only** → `ideas/`
- **No longer current but you still want the file in-repo** → `legacy/`

## Naming

- Prefer **kebab-case** file names.
- Keep tooling-standard root filenames (`README.md`, `CHANGELOG.md`, `AGENTS.md`, etc.) unchanged at repo root.

## Legacy pointer

Older references to `documentation-structure.md` still resolve; that file redirects here.
