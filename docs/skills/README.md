# Repo agent skills

Canonical, **vendor-neutral** playbooks for repeated agent work in this repo.
This is the implementation home for [`../specs/repo-agent-skills.md`](../specs/repo-agent-skills.md).

## What a skill is here

A skill is a small **procedural entry point** — a short workflow, trigger
guidance, and a validation checklist — for a kind of work that recurs. It is
**not** a second policy layer.

- Canonical content lives here as ordinary Markdown.
- Skills **point back** to canonical docs (`AGENTS.md`, the specs) instead of
  restating policy. If a skill and `AGENTS.md` ever disagree, `AGENTS.md` wins.
- Tool-specific wrappers (Cursor commands/rules, Claude `.claude/skills/…`,
  future Codex/Antigravity) stay **thin** and link back to the doc here, so no
  surface forks policy. See
  [`../contributing/ai-assisted-work.md`](../contributing/ai-assisted-work.md).

## Canonical skill shape

1. Purpose (and what it does *not* do).
2. When to use — trigger examples.
3. Workflow — short, ordered steps.
4. Canonical docs to read.
5. Validation checklist.
6. A `## Behavior Contract` (Gherkin) per
   [`../specs/behavior-contract-standard.md`](../specs/behavior-contract-standard.md).

Keep each skill concise. No copied `AGENTS.md` sections; no tool-specific
assumptions in the canonical doc.

## Skills

| Skill | Use it when | Doc |
| --- | --- | --- |
| `gittan-product-owner` | Prioritizing, shaping a backlog, slicing a feature, writing acceptance criteria. | [`gittan-product-owner.md`](gittan-product-owner.md) |
| `gittan-source-collector` | Adding or changing a data source / collector. | [`gittan-source-collector.md`](gittan-source-collector.md) |

More candidates (timelog-health, shadow-log, calendar, docs-foundation) are
described in [`../specs/repo-agent-skills.md`](../specs/repo-agent-skills.md) and
will be materialized here when needed.

## Tool wrappers

| Surface | Location |
| --- | --- |
| Cursor slash commands | [`../../.cursor/commands/`](../../.cursor/commands/) |
| Cursor scoped rules | [`../../.cursor/rules/`](../../.cursor/rules/) |
| Claude Code project skills | `.claude/skills/<name>/SKILL.md` (tracked via a `.gitignore` carve-out) |
