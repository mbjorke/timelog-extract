# Task Prompt: Browser-derived sources + mixed-session attribution (WordPress / Lovable web)

Unplanned but critical operator day (2026-07-09): continuous WordPress work was
credited to the wrong project and diluted by Lovable desktop cache pings +
Chrome weight 0. Timely showed ~6.5h on the client work; Gittan project-hour
review showed ~1.2h on a mislabeled profile and ~1.2h on an almost-idle client.
Classification and attribution had to be fixed before presence bracketing
(GH-332) can close the remaining observed-vs-Timely gap.

**Strategic frame:** Gittan must attribute *what* you worked on before it can
honestly claim *how long*. Derived browser sources (WordPress, Lovable web)
give Timely-like site identity without raising weight on all Chrome noise.
Presence bracketing remains the follow-up for total hours.

## Traceability

- story_id: `pending` — create via `/docs-to-issues` after this spec is committed
- spec_status: `draft`
- implementation_status: `in progress`
- created_at: `2026-07-09`
- last_updated_at: `2026-07-09`
- implementation.pr: pending
- implementation.branch: `task/wordpress-lovable-web-attribution`
- implementation.commits: []
- validation.evidence: operator `gittan-dev report --from 2026-07-09 --to 2026-07-09` — WordPress in legend; client WordPress hours 1.2h → 3.5h; idle Lovable client 1.2h → 0.0h; observed still 5.4h (presence gap → GH-332)
- validation.decision: `conditional GO` — attribution slice verified locally; presence undercount out of scope
- changelog:
  - `2026-07-09: Initial draft from unplanned WordPress-day incident + Timely comparison.`

## Problem

1. **Wrong source identity** — wp-admin and Lovable-in-Chrome were labeled
   generic `Chrome` (attribution weight 0), same bucket as Messenger/Jira tabs.
2. **Wrong allocation** — `Lovable (desktop)` weight 8 claimed Tier A high-signal
   spans; Chrome contributed nothing; remainder equal-split across every project
   in a 15-min-gap mixed session → idle Lovable/Messenger clients stole hours from
   dense WordPress work.
3. **Missing project profile** is a config/ops issue (private `~/.gittan`); the
   product gap is that Gittan did not surface a first-class WordPress *source*
   that could own spans once a profile exists.

## What already exists (do not rebuild)

- Chrome History collector (`collectors/chrome.py`) with derived sources
  `Claude.ai (web)` / `Gemini (web)`.
- `Lovable (desktop)` Electron collector under Application Support.
- Mixed-session allocation in `core/project_hours.py` (high-signal Tier A +
  weighted remainder).
- Presence bracketing spec: `docs/task-prompts/presence-bracketing-task.md`
  (GH-332) — **out of scope for this story**; closes observed 5.4h → Timely-like
  totals, not project split.

## Backlog

### Derived WordPress source + span-capable attribution

- priority: now
- problem: WordPress admin work looks like generic Chrome and loses hours in
  mixed sessions to Lovable/equal-split.
- user value: WordPress-heavy client days credit the right project without
  raising weight on all browsing.
- non-goals: WP REST/SFTP collectors; presence bracketing; auto-suggest new
  project configs from site titles (follow-up).
- behavior:

```gherkin
Scenario: WordPress admin visits are a distinct source
  Given a Chrome History visit whose title matches "‹ … — WordPress" or URL contains /wp-admin
  When collect_chrome runs
  Then the event source is "WordPress"
  And generic Chrome tabs remain source "Chrome"

Scenario: Dense WordPress work beats a lone Lovable desktop ping
  Given a mixed session with one Lovable (desktop) event for client-alpha
  And dense WordPress events for acme-news spanning most of the session
  When project-hour allocation runs
  Then acme-news receives the majority of session hours
  And client-alpha receives at most a short passive floor (not an equal split)

Scenario: Lovable web is distinct from Lovable desktop
  Given a Chrome visit to lovable.dev or *.lovableproject.com
  When collect_chrome runs
  Then the event source is "Lovable (web)"
  And Lovable Electron app events remain "Lovable (desktop)"
```

- acceptance:
  - `WordPress` and `Lovable (web)` registered in `SOURCE_ORDER`, roles,
    attended set, doctor rows, and evidence legend.
  - WordPress attribution weight span-capable (~3); Lovable (desktop) below
    high-signal floor (~4); Lovable (web) between Chrome and desktop (~2).
  - Tier B uses per-project sub-spans when weights cannot claim remainder;
    equal-split is last resort only.
  - Tests use synthetic fixtures only (no real client/person names).
- validation:
  - Unit tests for detection + allocation fixtures.
  - Operator report on a WordPress-heavy day: WordPress in legend; idle
    Lovable client hours collapse; WordPress client hours rise materially.
- dependencies: none for this slice; GH-332 for remaining total-hour gap.

### Propose new project from repeated WordPress site titles

- priority: next
- problem: a new WP site can be mis-attributed to an existing broad profile
  (e.g. generic `wordpress` match_terms) until a human adds a project.
- user value: `gittan map` / audit suggests "create project Acme News" from
  repeated `‹ Acme News — WordPress` titles.
- non-goals: silent auto-write of config without confirmation.
- behavior: (Gherkin when sliced) cluster unmapped WordPress site names →
  NewProjectProposal.
- acceptance: interactive propose + confirm; no silent overwrite of
  `timelog_projects.json`.
- validation: fixture with two WP sites, one mapped / one unmapped.
- dependencies: WordPress source shipped (now item).

### Presence bracketing for WordPress-heavy days

- priority: next (owned by GH-332)
- problem: observed timeline still undercounts vs Timely continuous presence
  even after attribution is correct.
- user value: session edges include ramp-up/ramp-down when Screen Time / Timely
  Memory show continuous presence.
- non-goals: inventing project identity from presence alone.
- behavior: see `presence-bracketing-task.md`.
- acceptance / validation: per GH-332.
- dependencies: this story's attribution slice (so bracketed minutes land on
  the right project).

### Raise all Chrome attribution weight

- priority: do not build yet
- problem: tempting shortcut for browser-heavy days.
- why not: inflates Messenger, Jira, and random tabs the same as WordPress.
- alternative: derived sources + span allocation (now) + presence bracketing
  (GH-332).

## Open decisions

- Promote WordPress from `passive_context` to `direct_work_evidence` after more
  operator days? Prefer keep passive + span weight until then.
- Should public-site titles without `— WordPress` (front-end only) count as
  WordPress source when host is a known WP `tracked_urls` host? Deferred —
  v1 uses title/`wp-admin` only.

## Related

- `docs/task-prompts/presence-bracketing-task.md` (GH-332)
- `docs/specs/source-evidence-policy.md`
- `core/project_hours.py`, `collectors/chrome.py`, `core/sources.py`
