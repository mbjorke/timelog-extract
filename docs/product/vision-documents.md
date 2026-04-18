# Gittan vision documents — how they relate

Use this file as the **index** when updating marketing copy or root `VISION.md` so all materials stay aligned.

## Precedence (source of truth)

If wording conflicts, use this order:

1. **`docs/product/gittan-vision.md`** — product soul, promises, decision filter, Blueberry/strategic mapping where applicable.
2. **`docs/product/v1-scope.md`** — what ships in which version; feature boundaries.
3. **`docs/product/gittan-northstar-metrics.md`** — measurable outcomes and KPIs tied to the vision.
4. **`docs/security/privacy-security.md`** — consent and data-handling guardrails.
5. **`VISION.md`** (repository root) — **short public manifesto** (e.g. Patreon, one-pagers). It must not contradict 1–4; when 1–4 change, refresh the root manifesto.

**`docs/product/gittan-vision-en.md`** is an English narrative companion to `docs/product/gittan-vision.md`; on conflict, `docs/product/gittan-vision.md` wins.

## Roles


| Document                                               | Role                                                                                                                                                                                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VISION.md`                                            | Punchy external story: problem, three pillars, and why to support the project — keep brief.                                                                                                                                  |
| `docs/business/patreon-positioning.md`                          | **Draft** fundraising copy and sponsor positioning notes (non-binding).                                                                                                                                                      |
| `docs/business/sponsorship-terms.md`                            | Legacy sponsorship-tier notes; no longer a legal license gate under GPL.                                                                                                                                                     |
| `docs/security/license-goals.md`                                | Non-binding explanation of why GPL-3.0 fits sustainability/open-source strategy.                                                                                                                                             |
| `docs/security/license-decision-matrix.md`                      | Historical license comparison notes; update if licensing strategy changes.                                                                                                                                                   |
| `docs/decisions/daily-repo-hygiene-routine.md`         | **Operational decision/routine:** daily 10-15 minute hygiene loop to keep release branches merge-ready and reduce review churn.                                                                                              |
| `docs/decisions/agent-inline-cli-ux-validation.md`     | **Operational decision/routine:** require inline `gittan` smoke checks during feature work so CLI UX is validated continuously, not only at PR end.                                                                           |
| `docs/product/gittan-vision.md`                                | Full vision: who it’s for, is/is not, roadmap links, decision filter.                                                                                                                                                        |
| `docs/product/gittan-vision-en.md`                             | English narrative + scope pointers.                                                                                                                                                                                          |
| `docs/product/gittan-northstar-metrics.md`                     | Metrics that operationalize the vision.                                                                                                                                                                                      |
| `docs/sources/activitywatch-integration.md`                    | **Backlog:** optional [ActivityWatch](https://activitywatch.net/) ingest — complementary local timeline signal; not shipped.                                                                                                 |
| `docs/runbooks/manual-test-matrix-0-2-x.md`                     | **Manual QA:** scenarios A/B/C (no config, CLI-only, minimal JSON) + optional checks; use before patch releases. **Partial automation:** `scripts/manual_matrix_automation.py` (`--deterministic`, optional `--last-month`). |
| `docs/product/worklog-first-strategy-plan.md`                  | **Roadmap plan:** worklog-first source strategy (`auto/worklog-first/balanced`), phased implementation, and acceptance criteria to reduce "empty" reports in repo-centric use.                                               |
| `docs/evals/latest.md`                                 | **Golden eval output** from `scripts/run_golden_eval.py` (see `docs/product/accuracy-plan.md`).                                                                                                                                      |
| `docs/runbooks/screen-time-gap-analysis.md`            | **Runbook:** Screen Time vs estimates gap export (`scripts/run_screen_time_gap_analysis.py`).                                                                                                                                  |
| `docs/product/future-notes-2026-04.md`               | **Working notes:** AI help scope, UI timing, calibration staging — ideas, not commitments.                                                                                                                                       |
| `tests/fixtures/golden_dataset.json`                   | **Expected hours** per (date, project) for the bundled worklog fixture; used by golden eval.                                                                                                                                 |
| `docs/sources/sources-and-flags.md`                            | **Behavior:** how collectors merge, source toggles vs `--exclude`, `collector_status` in JSON.                                                                                                                               |
| `docs/README.md`                                       | **Docs index:** where to place decisions, specs, runbooks, product, business, security, sources, ideas, incidents, and archives.                                                                                             |
| `docs/incidents/2026-04-15-coderabbit-review-command-misclick.md` | **Incident (operations):** accidental CodeRabbit review-command trigger; root cause, impact, and preventive checklist for review cadence.                                                                                     |
| `docs/ideas/ai-orchestration-source-estimation-learnings.md` | **Execution learning:** observed effort and estimation rubric for adding new data sources; checkpoint loop for more accurate AI-assisted planning.                                                                           |
| `docs/specs/ab-rule-suggestions.md`                    | **Active feature spec:** A/B rule-suggestion workflow for uncategorized activity, impact preview, and explicit apply confirmation.                                                                                           |
| `docs/specs/live-terminal-sandbox-demo.md`             | **Active feature spec:** secure deployable live terminal demo using sandboxed allowlisted command execution with deterministic fixture data.                                                                                  |
| `docs/task-prompts/ab-rule-suggestions-task.md`        | **Task execution prompt:** implementation checklist and acceptance criteria for A/B rule suggestions before release.                                                                                                           |
| `docs/task-prompts/agent-inline-cli-ux-validation-task.md` | **Task execution prompt:** priority implementation brief for automatic inline CLI smoke validation during agent-driven development.                                                                                              |
| `docs/task-prompts/copilot-cli-source-task.md`         | **Task story:** add first-class GitHub Copilot CLI source detection, collector wiring, doctor visibility, and source-summary reporting.                                                                                       |
| `docs/task-prompts/live-terminal-sandbox-demo-task.md` | **Task execution prompt:** secure live terminal demo rollout with allowlisted sandbox execution and hardening checklist.                                                                                                      |
| `docs/legacy/agentic-evaluation.md`                   | **Legacy technical evaluation:** early architecture/testability snapshot kept for historical context.                                                                                                                        |
| `docs/product/terminal-style-guide.md`                         | **UX semantics:** terminal typography, color roles, and low-noise output conventions for CLI commands.                                                                                                                       |
| `docs/sources/ai-assisted-config.md`                           | **Vision:** built-in assistant for `timelog_projects.json`; project names first; opt-in LLM; Jira-native vs solo workflows.                                                                                                  |
| `docs/runbooks/ci.md`                                           | **CI:** branch-protected `main`, workflow jobs, link to `.github/workflows/ci.yml`.                                                                                                                                          |
| `docs/legacy/release-scope-0.2.3.md`                 | **Release plan (historical):** must/should/nice scope for the **0.2.3** PyPI-first-upload milestone; linked from `docs/runbooks/versioning.md`.                                                                                       |
| `docs/ideas/opportunities.md`                          | **Product / GTM (ideas):** opportunities, risks, audience, differentiation—English; for business-style review.                                                                                                               |
| `docs/ideas/simple-invoicing-model.md`                 | **Solo-first integration model (idea):** export-first/push-only workflow, optional Lovable delivery layer, draft-first writes, and rollback guardrails before any broad API surface.                                        |
| `docs/brand/README.md`                                 | **Brand:** canonical marks, `drafts/` + `archive/`, generated `**gittan-logo.png`** + favicon/README/OG, `scripts/build_brand_assets.sh`.                                                                                    |
| `docs/brand/identity.md`                               | **Brand intent:** bumblebee pollinating berries + terminal frame, palette; optional drafts workflow.                                                                                                                            |
| `docs/meta/private-local-notes.md`                          | **Process:** where to keep gitignored `private/` business notes vs public docs.                                                                                                                                              |


## CLI vs Cursor extension

Product docs describe **local reporting engine first**; the **Cursor extension** is an evolving companion (see `GITTAN_VISION.md` maturity note and `README.md`). Root `VISION.md` may mention the extension as a **funding goal** or future UX; it should not imply the extension is required for core value — the CLI/script path is the primary v1 delivery.

## When you edit one, check the others

- Change **trust / local-first / scope** → update `docs/product/gittan-vision.md` first, then `VISION.md` and `docs/product/gittan-vision-en.md` if needed.
- Change **metrics or targets** → `docs/product/gittan-northstar-metrics.md` (+ `docs/product/accuracy-plan.md` where linked).
- Change **fundraising or public pitch only** → update `docs/business/patreon-positioning.md` (draft details) and/or `VISION.md` (short manifesto); both must stay consistent with 1–4.