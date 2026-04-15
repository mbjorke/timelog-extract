# Gittan vision documents — how they relate

Use this file as the **index** when updating marketing copy or root `VISION.md` so all materials stay aligned.

## Precedence (source of truth)

If wording conflicts, use this order:

1. `**docs/GITTAN_VISION.md`** — product soul, promises, decision filter, Blueberry/strategic mapping where applicable.
2. `**docs/V1_SCOPE.md`** — what ships in which version; feature boundaries.
3. `**docs/GITTAN_NORTHSTAR_METRICS.md`** — measurable outcomes and KPIs tied to the vision.
4. `**docs/PRIVACY_SECURITY.md`** — consent and data-handling guardrails.
5. `**VISION.md**` (repository root) — **short public manifesto** (e.g. Patreon, one-pagers). It must not contradict 1–4; when 1–4 change, refresh the root manifesto.

`**docs/GITTAN_VISION_EN.md`** is an English narrative companion to `GITTAN_VISION.md`; on conflict, `GITTAN_VISION.md` wins.

## Roles


| Document                                               | Role                                                                                                                                                                                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VISION.md`                                            | Punchy external story: problem, three pillars, and why to support the project — keep brief.                                                                                                                                  |
| `docs/PATREON_POSITIONING.md`                          | **Draft** fundraising copy and sponsor positioning notes (non-binding).                                                                                                                                                      |
| `docs/SPONSORSHIP_TERMS.md`                            | Legacy sponsorship-tier notes; no longer a legal license gate under GPL.                                                                                                                                                     |
| `docs/LICENSE_GOALS.md`                                | Non-binding explanation of why GPL-3.0 fits sustainability/open-source strategy.                                                                                                                                             |
| `docs/LICENSE_DECISION_MATRIX.md`                      | Historical license comparison notes; update if licensing strategy changes.                                                                                                                                                   |
| `docs/GITTAN_VISION.md`                                | Full vision: who it’s for, is/is not, roadmap links, decision filter.                                                                                                                                                        |
| `docs/GITTAN_VISION_EN.md`                             | English narrative + scope pointers.                                                                                                                                                                                          |
| `docs/GITTAN_NORTHSTAR_METRICS.md`                     | Metrics that operationalize the vision.                                                                                                                                                                                      |
| `docs/ACTIVITYWATCH_INTEGRATION.md`                    | **Backlog:** optional [ActivityWatch](https://activitywatch.net/) ingest — complementary local timeline signal; not shipped.                                                                                                 |
| `docs/MANUAL_TEST_MATRIX_0_2_x.md`                     | **Manual QA:** scenarios A/B/C (no config, CLI-only, minimal JSON) + optional checks; use before patch releases. **Partial automation:** `scripts/manual_matrix_automation.py` (`--deterministic`, optional `--last-month`). |
| `docs/WORKLOG_FIRST_STRATEGY_PLAN.md`                  | **Roadmap plan:** worklog-first source strategy (`auto/worklog-first/balanced`), phased implementation, and acceptance criteria to reduce "empty" reports in repo-centric use.                                               |
| `docs/evals/latest.md`                                 | **Golden eval output** from `scripts/run_golden_eval.py` (see `docs/ACCURACY_PLAN.md`).                                                                                                                                      |
| `tests/fixtures/golden_dataset.json`                   | **Expected hours** per (date, project) for the bundled worklog fixture; used by golden eval.                                                                                                                                 |
| `docs/SOURCES_AND_FLAGS.md`                            | **Behavior:** how collectors merge, source toggles vs `--exclude`, `collector_status` in JSON.                                                                                                                               |
| `docs/documentation-structure.md`                      | **Docs taxonomy:** where to place decisions, roadmap docs, ideas, specs, RC prompts, incidents, and archives.                                                                                                                |
| `docs/ideas/ai-orchestration-source-estimation-learnings.md` | **Execution learning:** observed effort and estimation rubric for adding new data sources; checkpoint loop for more accurate AI-assisted planning.                                                                           |
| `docs/specs/ab-rule-suggestions.md`                    | **Active feature spec:** A/B rule-suggestion workflow for uncategorized activity, impact preview, and explicit apply confirmation.                                                                                           |
| `docs/rc-prompts/ab-rule-suggestions-rc.md`            | **RC execution prompt:** implementation checklist and acceptance criteria for A/B rule suggestions before release.                                                                                                            |
| `docs/archive/agentic-evaluation.md`                   | **Archived technical evaluation:** early architecture/testability snapshot kept for historical context.                                                                                                                        |
| `docs/TERMINAL_STYLE_GUIDE.md`                         | **UX semantics:** terminal typography, color roles, and low-noise output conventions for CLI commands.                                                                                                                       |
| `docs/AI_ASSISTED_CONFIG.md`                           | **Vision:** built-in assistant for `timelog_projects.json`; project names first; opt-in LLM; Jira-native vs solo workflows.                                                                                                  |
| `docs/CI.md`                                           | **CI:** branch-protected `main`, workflow jobs, link to `.github/workflows/ci.yml`.                                                                                                                                          |
| `docs/archive/release-scope-0.2.3.md`                 | **Release plan (historical):** must/should/nice scope for the **0.2.3** PyPI-first-upload milestone; linked from `docs/VERSIONING.md`.                                                                                       |
| `docs/ideas/opportunities.md`                          | **Product / GTM (ideas):** opportunities, risks, audience, differentiation—English; for business-style review.                                                                                                               |
| `docs/ideas/simple-invoicing-model.md`                 | **Solo-first integration model (idea):** export-first/push-only workflow, optional Lovable delivery layer, draft-first writes, and rollback guardrails before any broad API surface.                                        |
| `docs/brand/README.md`                                 | **Brand:** canonical marks, `drafts/` + `archive/`, generated `**gittan-logo.png`** + favicon/README/OG, `scripts/build_brand_assets.sh`.                                                                                    |
| `docs/brand/IDENTITY.md`                               | **Brand intent:** rabbit + terminal frame, review-rabbit copy, palette; optional drafts workflow.                                                                                                                            |
| `docs/PRIVATE_LOCAL_NOTES.md`                          | **Process:** where to keep gitignored `private/` business notes vs public docs.                                                                                                                                              |


## CLI vs Cursor extension

Product docs describe **local reporting engine first**; the **Cursor extension** is an evolving companion (see `GITTAN_VISION.md` maturity note and `README.md`). Root `VISION.md` may mention the extension as a **funding goal** or future UX; it should not imply the extension is required for core value — the CLI/script path is the primary v1 delivery.

## When you edit one, check the others

- Change **trust / local-first / scope** → update `GITTAN_VISION.md` first, then `VISION.md` and `GITTAN_VISION_EN.md` if needed.
- Change **metrics or targets** → `GITTAN_NORTHSTAR_METRICS.md` (+ `ACCURACY_PLAN.md` where linked).
- Change **fundraising or public pitch only** → update `docs/PATREON_POSITIONING.md` (draft details) and/or `VISION.md` (short manifesto); both must stay consistent with 1–4.