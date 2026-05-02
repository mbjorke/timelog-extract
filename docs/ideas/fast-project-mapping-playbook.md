# Fast project mapping playbook (~10 minutes for a two-month window)

**Status:** working note (product + workflow). **Not** a shipped contract.

**Audience:** maintainers and power users tuning `timelog_projects.json` after the core collectors already run.

## Goal

Get from “rough config” to “good enough to trust for a retrospective window” in **roughly ten minutes** of focused work, **after** profiles and customer structure exist. First-time setup from zero usually takes longer because domain ownership decisions are human-latency, not tool-latency.

## Playbook (recommended order)

1. **Seed identities** — ensure git/bootstrap (or manual) has **repo slugs** (`owner/repo`) and project names in `match_terms` where those strings actually appear in traces.
2. **Anchor browsers first** — add `**tracked_urls`** for recurring hosts (customer portals, Jira/Atlassian host, GitHub org) *before* growing long phrase lists in `match_terms`. Site-first classification rewards stable domains.
3. **Route outgoing mail (optional, same mental model)** — If the Apple Mail source is enabled, **Sent** messages are classified from `**To` + `Subject*`* (headers only; no inbox, no body). Set `**email**` on each profile you send from (or pass `**--email**` on the CLI) so your **From** address passes the collector filter. Then add `**match_terms`** for strings that reliably appear in **recipient lines or subjects**—**customer domains in `To`** are usually the fastest win. This uses the same `classify_project` path as other sources; watch **shared domains** and vague subjects that could collide across projects. A **future** guided step could ask “outgoing domain → project?” and write these rules for you; until then, manual `match_terms` / `email` is the whole trick.
4. **Run `gittan projects-audit`** on the **same date range** you care about. Use hit counts to find **zero-hit** rules (candidates to remove later) and **misrouting** (overlap / wrong project).
5. **Run `gittan projects-lint`** — resolve cross-project `match_terms` overlap and risky broad terms before trusting totals.
6. **Disable dormant profiles** for the period under review — fewer competing buckets means fewer mis-assignments and less cognitive load.
7. **Trim conservatively** — use `gittan projects-trim` only for rules you are sure are obsolete; prefer a short observation window after audit before deleting rare-but-critical terms.
8. **Sanity-check the report** — skim **Uncategorized** and mixed sessions for the same window; fix the top one or two systematic gaps only.

## What this playbook does *not* solve by itself

- **Generic shared hosts** (e.g. `*.atlassian.net`) still need **explicit** per-project anchors; the product intentionally treats them as ambiguous without `tracked_urls`.
- `**default_client` / `customer` do not score Chrome domains** today — customer domains belong in `**tracked_urls`** or domain-shaped `**match_terms**` when you need host-level routing.
- **Triage gap flows** (`gittan triage`, `gittan triage-domains`) depend on **unexplained Screen Time** / plan structure; they complement audit but do not replace “count what fired” for rule hygiene.
- **Mail:** only **Sent** mail is ingested; **inbox / flagged threads / body text** are not part of the current collector—only what appears in **To/Subject** can drive classification.