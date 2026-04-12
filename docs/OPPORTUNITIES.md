# Opportunities — product and go-to-market (working document)

**Status:** Living notes for **business / product** review (e.g. CodeRabbit follow-ups, human advisors). **Not** legal advice. Public repo copy stays aligned with `LICENSE`, `docs/SPONSORSHIP_TERMS.md`, and `docs/VISION_DOCUMENTS.md`.

**Scope:** Strategic narrative and risks—not **tactical marketing** (channel plans, post drafts). Put those in a **gitignored** `private/` tree; see **`docs/PRIVATE_LOCAL_NOTES.md`**.

**Language:** English-only for documentation in this repository (see `CONTRIBUTING.md` and PR language rules).

---

## One-sentence thesis

**Gittan / Timelog Extract** turns fragmented local traces (IDE, browser, worklog, optional APIs) into **defensible, project-aware time reports**—**local-first**, scriptable CLI, versioned JSON for automation—so people who **bill or explain time** can trust the story without surrendering data to a cloud timetracker.

---

## Who it is for (now vs aspiration)

| Layer | Audience |
|-------|-----------|
| **Primary (today)** | People comfortable in a **terminal**—typically **dev / ops**—who already stitch tools together and will run `gittan` or scripts. |
| **Aspirational** | *Anyone* who has wished for **automatic time reporting**; messaging can invite that dream without promising zero-friction GUI parity on day one. |
| **Strategic bonus** | Users who become **curious about terminal UX**—efficiency, composability, piping JSON—vs heavy GUI; CLI-first is a **differentiator**, not a compromise apology. |

---

## What “v1 ready” means for marketing

- **Ready to market with pride** (e.g. LinkedIn) when the story and shipped scope feel **honest**—not when every dream feature exists.
- **Later waves** (e.g. around **0.2.3-style** milestones) may explicitly seek **test partners** (“test rabbits”)—language TBD; keep **consent and expectations** clear in public posts.

---

## Product bets (from current direction)

1. **CLI-first is the long-term “wow.”** Rich output, `gittan`, JSON truth payload, automation—this is the core experience worth amplifying.
2. **Cursor / IDE extension** is **not** the hero path; companion GUI work may be **deprioritized or dropped** in favor of engine + terminal story.
3. **Simplify project configuration** — **High priority:** make `timelog_projects.json` easier to create and maintain (clearer defaults, validation users can act on, guided flows, fewer sharp edges) so classification is not a specialist-only task. This is partly **incremental UX/engine work** and partly the longer **AI-assisted authoring** vision in **`docs/AI_ASSISTED_CONFIG.md`** (optional cloud LLM with user API key **and/or** local LLM)—the vision doc stays the north star; shipping can start with non-LLM simplifications.
4. **Integrations (backlog):** **Calendar / CalDAV** and optional **ActivityWatch**-style ingest are **candidates**, not commitments—priority TBD against solo-founder value and maintenance cost.
5. **Enterprise issue trackers** (Jira, Linear) are **later**; **solo / founder** workflows and honest reporting come first.

---

## Differentiation (honest)

- **Local execution** and **user-owned data** vs SaaS timetrackers.
- **Evidence-oriented** narrative (sessions, sources, optional PDF) vs “trust our black box.”
- **Terminal + JSON** for people who want **repeatable** runs in CI, scripts, or extensions—**without** locking the core behind a GUI.

---

## Risks (product)

- **Keyword / profile burden:** Good coverage may require thoughtful `match_terms`; **zero-config** can feel empty until users understand Chrome pre-filtering and Uncategorized behavior (see `docs/SOURCES_AND_FLAGS.md`, `docs/MANUAL_TEST_MATRIX_0_2_x.md`). Mitigation is tied to the **simplify project configuration** bet above and to **`docs/AI_ASSISTED_CONFIG.md`** over time.
- **Collector maintenance:** App vendors change log paths and formats; quality depends on **fixtures** and **clear disable reasons** in reports.
- **Expectation gap:** “Automatic” is **reconstruction + rules**, not mind-reading; calendar and chat integrations would **change** the story when shipped.

---

## Funding and sustainability (high level)

- The repo ships under the **Gittan / Timelog Extract License** (see `LICENSE`)—professional-scale use may map to **sponsorship tiers** described in **`docs/SPONSORSHIP_TERMS.md`**.
- **Go-to-market** should lead with **product value**; **sustainability** can be multiple channels over time (not a single fixed playbook). Draft fundraising copy in `docs/PATREON_POSITIONING.md` is **non-binding** until aligned with legal docs.
- **Planned — GitHub Funding / Sponsors wiring:** Use GitHub’s flow to add **Sponsor** button metadata (typically `.github/FUNDING.yml` on `main`): [open funding setup for this repo](https://github.com/mbjorke/timelog-extract/new/main?repository_funding=1). Align listed URLs with **`docs/SPONSORSHIP_TERMS.md`** and your live Patreon (or other) pages before merging.
- **Planned — GitHub Discussions (announcements):** Turn on **Discussions** for the repo if needed; use the **Announcements** category for rare, high-signal posts. Composer with welcome helper: [new discussion — announcements + welcome text](https://github.com/mbjorke/timelog-extract/discussions/new?category=announcements&welcome_text=true).
- **Planned — GitHub issue templates:** Configure **issue templates** (bug report, feature, etc.) in the web UI: [edit issue templates](https://github.com/mbjorke/timelog-extract/issues/templates/edit). Keep prompts aligned with **`CONTRIBUTING.md`** and what CI / `docs/CI.md` actually checks.
- **Planned — Social preview (Open Graph):** GitHub shows a **repository image** when links are shared (social, Slack, etc.). Upload under **Settings → General → Social preview** in the [repository settings](https://github.com/mbjorke/timelog-extract/settings). **Minimum 640×320px**; **1280×640px recommended.** Source asset in-repo: **`repository-open-graph-template.png`** (1280×640) — customize branding/text, export at that size, then upload the final PNG in GitHub (the uploaded file is stored by GitHub, not read live from the repo).

---

## Sensitive material (not in git)

Business plans, unpublished pricing experiments, and **LinkedIn drafts** that are not ready to share should live in a **local-only** place—see **`docs/PRIVATE_LOCAL_NOTES.md`**. That keeps the public repo reviewable while preserving a private working surface.

---

## Questions for external review (optional checklist)

Use these in PR comments or advisor sessions when you want a **second brain** on the business layer:

1. Does this PR **strengthen or dilute** the CLI-first / local-first story?
2. Who **benefits most**—solo consultant, small team, or internal champion in a larger org?
3. Any **messaging risk** in README / VISION / new docs (overclaim, scope creep, competitor comparison)?
4. Does the **LICENSE / sponsorship** story still match how we describe the product publicly?
5. What is the **single next bet** (calendar, **simplified project config**, integrations) that best matches “market with pride”?

---

## Company context (public facts from repo)

**Blueberry Maybe Ab Ltd** appears as copyright holder in `LICENSE`. Keep marketing and legal text consistent with that file and with `docs/SPONSORSHIP_TERMS.md` when publishing tiers or obligations.
