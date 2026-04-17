# Opportunities — product and go-to-market (working document)

**Status:** Living notes for **business / product** review (e.g. CodeRabbit follow-ups, human advisors). **Not** legal advice. Public repo copy stays aligned with `LICENSE` and `docs/vision-documents.md`.

**Scope:** Strategic narrative and risks—not **tactical marketing** (channel plans, post drafts). Put those in a **gitignored** `private/` tree; see `**docs/private-local-notes.md`**.

**Language:** English-only for documentation in this repository (see `CONTRIBUTING.md` and PR language rules).

---

## One-sentence thesis

**Gittan / Timelog Extract** turns fragmented local traces (IDE, browser, worklog, optional APIs) into **defensible, project-aware time reports**—**local-first**, scriptable CLI, versioned JSON for automation—so people who **bill or explain time** can trust the story without surrendering data to a cloud timetracker.

---

## Who it is for (now vs aspiration)


| Layer               | Audience                                                                                                                                                         |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Primary (today)** | People comfortable in a **terminal**—typically **dev / ops**—who already stitch tools together and will run `gittan` or scripts.                                 |
| **Aspirational**    | *Anyone* who has wished for **automatic time reporting**; messaging can invite that dream without promising zero-friction GUI parity on day one.                 |
| **Strategic bonus** | Users who become **curious about terminal UX**—efficiency, composability, piping JSON—vs heavy GUI; CLI-first is a **differentiator**, not a compromise apology. |


---

## What “v1 ready” means for marketing

- **Ready to market with pride** (e.g. LinkedIn) when the story and shipped scope feel **honest**—not when every dream feature exists.
- **Later waves** (e.g. around **0.2.3-style** milestones) may explicitly seek **test partners** (“test rabbits”)—language TBD; keep **consent and expectations** clear in public posts.

---

## Product bets (from current direction)

1. **CLI-first is the long-term “wow.”** Rich output, `gittan`, JSON truth payload, automation—this is the core experience worth amplifying.
2. **Cursor / IDE extension** is **not** the hero path; companion GUI work may be **deprioritized or dropped** in favor of engine + terminal story.
3. **Simplify project configuration** — **High priority:** make `timelog_projects.json` easier to create and maintain (clearer defaults, validation users can act on, guided flows, fewer sharp edges) so classification is not a specialist-only task. This is partly **incremental UX/engine work** and partly the longer **AI-assisted authoring** vision in `**docs/ai-assisted-config.md`** (optional cloud LLM with user API key **and/or** local LLM)—the vision doc stays the north star; shipping can start with non-LLM simplifications.
4. **Integrations (backlog):** **Calendar / CalDAV** and optional **ActivityWatch**-style ingest are **candidates**, not commitments—priority TBD against solo-founder value and maintenance cost.
5. **Enterprise issue trackers** (Jira, Linear) are **later**; **solo / founder** workflows and honest reporting come first.

## Solo-first cloud delivery stance

- **Preferred near-term shape:** local-first preparation in Gittan, optional cloud
delivery through a middle layer (Lovable) for drafting, styling, recipient handling,
and email send workflow.
- **Why now:** this keeps user control explicit (review before upload, explicit send),
while avoiding early complexity from broad inbound API design and long-lived tokens.
- **Promise boundary:** do not imply automatic background sync; frame this as
user-triggered export/upload and draft-first cloud workflow.
- **Out of scope for this phase:** generic query API surface, bi-directional sync, and
enterprise-grade multi-tenant auth/permission systems.

---

## Differentiation (honest)

- **Local execution** and **user-owned data** vs SaaS timetrackers.
- **Evidence-oriented** narrative (sessions, sources, optional PDF) vs “trust our black box.”
- **Terminal + JSON** for people who want **repeatable** runs in CI, scripts, or extensions—**without** locking the core behind a GUI.

---

## Risks (product)

- **Keyword / profile burden:** Good coverage may require thoughtful `match_terms`; **zero-config** can feel empty until users understand Chrome pre-filtering and Uncategorized behavior (see `docs/sources-and-flags.md`, `docs/manual-test-matrix-0-2-x.md`). Mitigation is tied to the **simplify project configuration** bet above and to `**docs/ai-assisted-config.md`** over time.
- **Collector maintenance:** App vendors change log paths and formats; quality depends on **fixtures** and **clear disable reasons** in reports.
- **Expectation gap:** “Automatic” is **reconstruction + rules**, not mind-reading; calendar and chat integrations would **change** the story when shipped.

---

## Funding and sustainability (high level)

- The repo ships under **GNU GPL-3.0-or-later** (see `LICENSE`).
- **Go-to-market** should lead with **product value**; **sustainability** can be multiple channels over time (not a single fixed playbook). Draft fundraising copy in `docs/patreon-positioning.md` is non-binding positioning material.
- **Planned — GitHub Funding / Sponsors wiring:** Use GitHub’s flow to add **Sponsor** button metadata (typically `.github/FUNDING.yml` on `main`): [open funding setup for this repo](https://github.com/mbjorke/timelog-extract/new/main?repository_funding=1). Align listed URLs with live Patreon/Sponsors pages before merging.
- **GitHub Discussions:** **[Discussions home](https://github.com/mbjorke/timelog-extract/discussions)** — default **General** / **Q&A** for community feedback and install questions (replaces the old in-repo pilot feedback file). **Announcements** for rare maintainer posts: [new discussion — announcements + welcome text](https://github.com/mbjorke/timelog-extract/discussions/new?category=announcements&welcome_text=true).
- **Planned — GitHub issue templates:** Configure **issue templates** (bug report, feature, etc.) in the web UI: [edit issue templates](https://github.com/mbjorke/timelog-extract/issues/templates/edit). Keep prompts aligned with `**CONTRIBUTING.md`** and what CI / `docs/ci.md` actually checks.
- **Planned — Social preview (GitHub repo):** When links to **this repository** are shared, GitHub can show a **repository card image**. Upload under **Settings → General → Social preview** in the [repository settings](https://github.com/mbjorke/timelog-extract/settings). **Minimum 640×320px**; **1280×640px recommended.** Start from in-repo `**repository-open-graph-template.png`**, export a final PNG, and upload in Settings (GitHub stores it; not read live from the repo).
- **Brand assets (in-repo):** Canonical masters `**docs/brand/gittan-brand-mark.png`** + `**gittan-og-card.png`**; experiments in `**docs/brand/drafts/**`; snapshots in `**docs/brand/archive/**`. Derived `**favicon.ico**`, `**gittan-readme-icon.png**`, root `**gittan-logo.png**` (landing nav/hero), `**og-image.png**` via `**scripts/build_brand_assets.sh**`. `gittan.html` uses `**/gittan-logo.png**`; meta uses `https://gittan.sh/og-image.png` after Pages deploy.

---

## Sensitive material (not in git)

Business plans, unpublished pricing experiments, and **LinkedIn drafts** that are not ready to share should live in a **local-only** place—see `**docs/private-local-notes.md`**. That keeps the public repo reviewable while preserving a private working surface.

---

## Questions for external review (optional checklist)

Use these in PR comments or advisor sessions when you want a **second brain** on the business layer:

1. Does this PR **strengthen or dilute** the CLI-first / local-first story?
2. Who **benefits most**—solo consultant, small team, or internal champion in a larger org?
3. Any **messaging risk** in README / VISION / new docs (overclaim, scope creep, competitor comparison)?
4. Does the **license / funding** story still match how we describe the product publicly?
5. What is the **single next bet** (calendar, **simplified project config**, integrations) that best matches “market with pride”?

---

## Company context (public facts from repo)

**Blueberry Maybe AB** appears as copyright holder in `LICENSE`. Keep marketing and legal text consistent with that file when publishing public copy.