# Fast project mapping playbook (~10 minutes for a two-month window)

**Status:** working note (product + workflow). **Not** a shipped contract.

**Audience:** maintainers and power users tuning `timelog_projects.json` after the core collectors already run.

## Goal

Get from “rough config” to “good enough to trust for a retrospective window” in **roughly ten minutes** of focused work, **after** profiles and customer structure exist. First-time setup from zero usually takes longer because domain ownership decisions are human-latency, not tool-latency.

## Locked model (current standard)

- Primary worklog model: per-project files in `~/.gittan/worklogs/<project-id>.md`.
- Store each path in the project profile as `"worklog"` in `timelog_projects.json`.
- `TIMELOG.md` is legacy fallback compatibility, not the recommended default.
- Mapping actions are performed via `projects-audit` / `projects-trim`; `status` / `report` are signal surfaces, not interactive mapping wizards.

## Playbook (recommended order)

1. **Seed identities** — ensure git/bootstrap (or manual) has **repo slugs** (`owner/repo`) and project names in `match_terms` where those strings actually appear in traces.
2. **Anchor browsers with high precision** — add `tracked_urls` for project-specific hosts/paths first (customer portals, project pages, repo-specific URLs) *before* growing phrase lists in `match_terms`. Avoid generic roots (`github.com`, `claude.ai`, `lovable.dev`) unless manually justified.
3. **Route outgoing mail (optional, same mental model)** — If the Apple Mail source is enabled, **Sent** messages are classified from `To` + `Subject` (headers only; no inbox, no body). Set `email` on each profile you send from (or pass `--email` on the CLI) so your **From** address passes the collector filter. Then add `match_terms` for strings that reliably appear in recipient lines or subjects—customer domains in `To` are usually the fastest win. This uses the same `classify_project` path as other sources; watch **shared domains** and vague subjects that could collide across projects. A **future** guided step could ask “outgoing domain → project?” and write these rules for you; until then, manual `match_terms` / `email` is the whole trick.
4. **Run `gittan projects-audit`** on the **same date range** you care about. Use hit counts to find **zero-hit** rules (candidates to remove later) and **misrouting** (overlap / wrong project). The JSON output (and terminal table when not `--json`) includes `top_hosts`: frequent http(s) hosts parsed from traces, with `anchored` = whether your current `match_terms` / `tracked_urls` already tie that host to a rule — prioritize **unanchored** high-hit hosts for new *specific* `tracked_urls`.
5. **Run `gittan projects-lint`** — resolve cross-project `match_terms` overlap and risky broad terms before trusting totals.
6. **Disable dormant profiles** for the period under review — fewer competing buckets means fewer mis-assignments and less cognitive load.
7. **Trim conservatively** — use `gittan projects-trim` only for rules you are sure are obsolete; prefer a short observation window after audit before deleting rare-but-critical terms.
8. **Sanity-check the report** — skim **Uncategorized** and mixed sessions for the same window; fix the top one or two systematic gaps only. If you need actionable mapping decisions, return to `projects-audit` (not inline report prompts).

## What this playbook does *not* solve by itself

- **Generic shared hosts** (e.g. `*.atlassian.net`) still need **explicit** per-project anchors; the product intentionally treats them as ambiguous without `tracked_urls`.
- `**default_client` / `customer`** do not score Chrome domains today — customer domains belong in `tracked_urls` or domain-shaped `match_terms` when you need host-level routing.
- **Triage gap flows** (`gittan triage`, `gittan triage-domains`) depend on **unexplained Screen Time** / plan structure; they complement audit but do not replace “count what fired” for rule hygiene.
- **Mail:** only **Sent** mail is ingested; **inbox / flagged threads / body text** are not part of the current collector—only what appears in **To/Subject** can drive classification.
- **Worklogs:** recommended source is per-project `~/.gittan/worklogs/<project-id>.md` via explicit profile `worklog` paths; repo-local `TIMELOG.md` is legacy fallback.

## CLI quick reference

Replace paths and dates with your own. Default audit window when no `--from` / `--to` / relative flags are passed is the **last seven days** (see `gittan projects-audit --help`).

```bash
# Usage audit for a fixed window (table output)
gittan projects-audit --from YYYY-MM-DD --to YYYY-MM-DD --projects-config /path/to/timelog_projects.json

# Same window, JSON (schema v1; stdout only). Includes `top_hosts` (host, hits, anchored).
gittan projects-audit --from YYYY-MM-DD --to YYYY-MM-DD --projects-config /path/to/timelog_projects.json --json

# Fewer rows in top_hosts table / JSON (default 30; use 0 to omit host mining)
gittan projects-audit --from YYYY-MM-DD --to YYYY-MM-DD --projects-config /path/to/timelog_projects.json --max-top-hosts 20

# Write a trim-plan file (schema v1): removals = zero-hit rules in this window only — review before apply
gittan projects-audit --from YYYY-MM-DD --to YYYY-MM-DD --projects-config /path/to/timelog_projects.json --write-trim-plan /path/to/trim-plan.json

# Structural warnings (overlaps, risky broad terms)
gittan projects-lint --config /path/to/timelog_projects.json

# Optional: strict exit code when warnings exist
gittan projects-lint --config /path/to/timelog_projects.json --strict
```

**Trim** (after you are sure a rule is obsolete — prefer `projects-audit` evidence first). You can hand-edit JSON or start from `--write-trim-plan` (candidates only; never auto-applied):

```bash
# removals.json top-level shape:
# {"schema_version": 1, "removals": [{"project_name": "My Project", "rule_type": "match_terms", "rule_value": "old-token"}]}

gittan projects-trim --projects-config /path/to/timelog_projects.json -i removals.json --dry-run
gittan projects-trim --projects-config /path/to/timelog_projects.json -i removals.json
```

**Report sanity check** for the same window you audited:

```bash
gittan report --from YYYY-MM-DD --to YYYY-MM-DD --projects-config /path/to/timelog_projects.json --screen-time off --source-summary
```

## Related docs

- `[docs/task-prompts/projects-config-trimming-task.md](../task-prompts/projects-config-trimming-task.md)` — shipped CLI scope for audit/trim.
- `[docs/runbooks/gittan-triage-agents.md](../runbooks/gittan-triage-agents.md)` — read-only triage JSON vs apply paths (`triage-apply`); distinct from `projects-audit --json`.
- `[docs/runbooks/classification-trust-recovery.md](../runbooks/classification-trust-recovery.md)` — when totals feel wrong end-to-end.

