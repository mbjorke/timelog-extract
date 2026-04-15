# Gittan / Timelog Extract — Launch Review

**Date:** 2026-04-11  
**Version:** 0.2.0  
**Reviewer:** Claude (claude/gittan-launch-review-4a5DD)  
**Scope:** Code quality + business strategy review for v1 launch readiness

> Historical note: this review predates the later repository-wide move to GPL-3.0-or-later.

---

## Executive Summary

Gittan is genuinely ready to market. The product solves a real pain, the privacy-first
positioning is credible and technically grounded, and the documentation depth is unusual
for a solo-founder project at this stage. The single honest blocker is distribution, not
product.

One security finding was fixed as part of this review (SQL injection in the Chrome
collector — parameterized queries now used throughout `collectors/chrome.py`).

---

## Part I — Code Review

### 1. Code quality assessment for 1.0 release

**Overall grade: B+**

The architecture is clean. The engine API boundary (`core/engine_api.py`) is the right
call and it's well-executed: a stable, extension-facing surface that keeps the extension
from importing collector internals. Type hints are used consistently. Collectors fail
gracefully — a broken Chrome database or missing mail folder won't crash the whole run.

Issues that exist are real but not launch-blocking:

| Finding | Severity | Notes |
|---|---|---|
| SQL injection in `chrome.py` | HIGH | **Fixed in this review** (parameterized queries) |
| `cli_doctor_sources_projects.py` ~15 KB | MEDIUM | Violates documented 500-line policy; hard to test |
| `report_runtime.py` / `cli_report_status.py` oversized | LOW | Same policy; lower urgency |
| `config.py` silently swallows `JSONDecodeError` | LOW | Returns fallback; caller can't distinguish |
| Collectors skip malformed entries without logging count | LOW | Makes debugging collection gaps harder |

The SQL injection (in `chrome.py` functions `collect_claude_ai_urls()`,
`collect_gemini_web_urls()`, and `collect_chrome()`) used f-string interpolation
of user-controlled project names and keywords into LIKE clauses. Since this is a
local-only tool reading the user's own browser database, the practical exploitability is
low — but the bug could cause silent SQL errors when project names contain `%` or `'`,
which would silently drop Chrome events from a report. Now fixed.

### 2. Technical debt that would block scaling to 100+ users

Nothing that blocks distribution. Issues to address before 100 concurrent users *of a
shared service* would be different, but Gittan is local-first — each user runs their own
instance. The relevant scaling concern is *maintainability at scale of the codebase*, not
runtime scaling.

The one item that would genuinely create maintenance burden at scale:
`cli_doctor_sources_projects.py` is ~15 KB in a single file. When collectors are added,
this file will become a maintenance trap. Splitting it by source category would take one
afternoon and should happen before v1.

Everything else — the collector registry, the pipeline, the engine API — scales
comfortably.

### 3. Security/privacy implementation review — does it hold up?

**Local-first claim: verified.**

- No outbound connections in the core flow. The only collector that makes network
  requests is `collectors/github.py`, which calls the public GitHub events API using the
  user's own token. This is documented and expected.
- Browser history, Mail, and Screen Time are off by default. The consent architecture
  in `PRIVACY_SECURITY.md` matches what the code actually does.
- Credentials are read from environment variables only (`GITHUB_TOKEN`). No credential
  storage in project files.
- Chrome history is read via a temp-file copy, not the live database. The temp file is
  cleaned up in a `finally` block.

The "privacy-first" claim is not marketing — it's structurally enforced. The code
cannot phone home without significant changes.

**Remaining gap:** there is no first-run consent gate in the current CLI. `PRIVACY_SECURITY.md`
and `V1_FINISH_PLAN.md` both list this as an M1 milestone. Ship the consent gate before
calling it v1 — not because the tool is unsafe, but because the absence of it makes the
privacy claim feel weaker to a first-time user who reads the source.

### 4. Maintainability vs solo-founder burden

The codebase is maintainable for one person at this scope. A few concrete observations:

- The collector registry pattern means adding a new source is localized: write the
  collector, register it, done. No spider-web imports.
- The `engine_api.py` surface is thin and stable. The extension won't break when
  internals change.
- The 500-line file policy is a good heuristic. It is currently violated in
  `cli_doctor_sources_projects.py`. Enforce it now, before it becomes a bigger problem.
- Test count (46 tests, ~835 lines) is adequate for the current scope. As the collector
  count grows, fixture-driven tests (`V1_FINISH_PLAN.md` M2) will become necessary.

**Solo-founder risk:** the TIMELOG.md worklog pattern is a manual override that requires
discipline to maintain. The system works well when it's used consistently, but there is
no enforcement or reminder mechanism. This is fine for v1 but worth noting for any user
who has a less-structured workflow than the author.

### 5. Test coverage adequate for production?

**Adequate for the current stage; not for long-term stability.**

- 46 tests cover happy paths, core domain logic, service boundary contracts, engine API,
  and regression locks.
- Error paths are under-tested. No tests for: malformed Chrome database, missing
  permissions on Mail folders, bad JSON in `timelog_projects.json`, GitHub API rate
  limiting.
- No tests for the Chrome collector specifically after the SQL injection fix. Add at
  least one parametrized test with a project name containing `%` and `'` to prevent
  regression.
- The `V1_FINISH_PLAN.md` M2 milestone (fixture-driven parser tests + CI gating) is the
  right next step for test coverage. It is not a v0.2.0 blocker but should be a v1 gate.

**Recommendation:** Add a regression test for the SQL injection fix before tagging v1.

---

## Part II — Business Strategy Review

### 1. Is the `/docs` strategy coherent and launch-ready?

**Yes, with one structural gap.**

The strategy documents are unusually thorough for a solo project. `docs/ideas/opportunities.md`,
`GITTAN_NORTHSTAR_METRICS.md`, `SPONSORSHIP_TERMS.md`, and `V1_FINISH_PLAN.md` form a
coherent whole. The metrics are specific and measurable. The finish plan has realistic
exit criteria per milestone.

The structural gap: no concrete launch date exists anywhere in the docs. The checklist
(`CLI_FIRST_V1_RELEASE_CHECKLIST.md`) has a status snapshot but no target date. The
v1 finish plan has a "two-week execution sequence" but no start date anchored to it.
Without a date, "awaiting feedback from Andreas/Pierre" can drift indefinitely.

**Action:** Set a launch date. Write it in `CLI_FIRST_V1_RELEASE_CHECKLIST.md` as a
committed line: `Target v1 tag: [date]`. This is the most important single thing to do
after this review.

### 2. Are pricing tiers realistic for the developer tool market?

**Yes. The tiers are conservative, which is appropriate for an unproven audience.**

| Tier | Price | Verdict |
|---|---|---|
| Supporter | ~$5/mo | Correct anchor for individual goodwill |
| Power User | ~$15/mo | Right for early-access + extension value |
| Agency/hands-on | ~$50/mo | Undersells the hands-on time; consider $75–100 |

The Agency tier promises "direct setup help for complex `timelog_projects.json` + custom
PDF branding." At €70/hr (your consulting rate), three hours of setup help costs €210.
$50/month is a steep discount. Either raise the tier to $75–100 or tighten the SLA
language to cap included hours at 1-2 per month.

The Power User tier at $15 is well-positioned. Early-access framing works well for
developers who want to influence the roadmap.

The free tier (1-2 users per org under the license) is the right call for adoption. Do
not remove it.

### 3. Is Patreon + LinkedIn sufficient for the first 100 users?

**No. Not as the only channels.**

LinkedIn will reach people who already know Marcus. It is good for warm leads and
testimonials from existing clients. It will not generate cold discovery at volume.

Patreon is a funding mechanism, not a discovery channel. People do not browse Patreon
looking for developer tools.

To reach 100 users, the product needs to appear where developers look for tools:

| Channel | Effort | Expected yield |
|---|---|---|
| Hacker News "Show HN" | 2-4 hours to write | High variance; potential for 200+ in 48h or 5 |
| Reddit r/selfhosted | 30 minutes | Steady trickle; good fit for local-first angle |
| Reddit r/devtools | 30 minutes | Direct audience match |
| Product Hunt | Half-day to set up | Moderate; better for visibility than conversion |
| dev.to or similar blog post | 3-4 hours | Long tail; builds SEO |
| Direct outreach to 5-10 developer newsletters | 1-2 hours | High conversion if accepted |

The privacy-first + local-only angle is a genuine hook for the current moment (2026,
post-data-scandal climate). Lead with it in the Show HN title. Do not lead with "time
tracker" — that sounds like Toggl. Lead with "I built a local-only tool that reads your
git, Cursor, and Claude logs to reconstruct a defensible time report."

The first 100 users will not come from Patreon. They will come from a Show HN, a
Reddit post, or a newsletter mention. Patreon is where they go *after* they decide they
want to support the project.

### 4. What is the single biggest risk pre-launch?

**No-launch drift.**

The product is ready. The docs are ready. The technology is not the risk.

The risk is that "awaiting feedback from Andreas/Pierre" becomes the permanent state. One
week becomes two. The launch date never gets set. The Patreon never goes live. The
Show HN post never gets written.

This risk is familiar to solo founders. The mitigation is boring but effective: set a
public date and tell one person about it. The feedback from Andreas or Pierre is useful
but not required to ship. Use their feedback to improve the Show HN post, not as a gate
to publishing the Patreon.

The second-biggest risk is underselling the privacy differentiation. Every paragraph
about Gittan should lead with "local-only" before mentioning features. The market is
tired of SaaS surveillance. This is a genuine advantage and it needs to be the first
thing a visitor reads.

### 5. Does the LICENSE + SPONSORSHIP_TERMS.md story make sense?

**Yes, but the onboarding path needs one sentence of explanation.**

The license structure is coherent: source-available, free for 1-2 professional users,
Patreon required at team scale. `LICENSE_GOALS.md` explains the intent clearly. The
normative tier mapping in `SPONSORSHIP_TERMS.md` is precise and reviewable.

The risk is that a developer landing on the repo for the first time sees an unfamiliar
license name and closes the tab. MIT and Apache-2.0 have Pavlovian trust. "Gittan/Timelog
Extract License" does not.

**Mitigation:** Add two sentences to the README under the license badge, before any
feature description:

> "Source-available — full source visible, free for individuals and pairs. Team use
> (3+ users in one org) requires a Patreon subscription. See LICENSE and
> SPONSORSHIP_TERMS.md."

This converts a potential objection into a transparent, reasonable policy. Developers
who encounter this framing and disagree will self-select out early. Developers who
appreciate honesty will respect it.

One additional note: `SPONSORSHIP_TERMS.md` references a Patreon URL as "TBD before
first release expecting paid sponsorship at scale." Create the Patreon page before the
Show HN post. The page does not need to be perfect. It needs to exist.

---

## Summary: What to Do Next, in Order

1. **Set a launch date.** Write it in `CLI_FIRST_V1_RELEASE_CHECKLIST.md`. Today.
2. **Create the Patreon page.** Imperfect is fine. It must exist before you post.
3. **Add README license clarity.** Two sentences under the license badge.
4. **Write the Show HN post.** Lead with "local-only" and "your git/Cursor/Claude logs."
5. **Ship M1 consent gate** from `V1_FINISH_PLAN.md` before tagging v1.
6. **Add a regression test** for the SQL injection fix in `collectors/chrome.py`.
7. **Split `cli_doctor_sources_projects.py`** before it grows further.

Items 1–4 are business. Items 5–7 are engineering. Items 1–4 are more urgent.

---

## Security Fix Applied in This Review

**File:** `collectors/chrome.py`  
**Issue:** f-string interpolation of project names and URL keywords into SQLite LIKE
clauses. Values containing `%`, `'`, or other SQL-significant characters could cause
silent query failures, dropping Chrome events from reports.  
**Fix:** Parameterized queries throughout — `query_chrome()` now accepts a `params`
tuple; all three call sites (`collect_claude_ai_urls`, `collect_gemini_web_urls`,
`collect_chrome`) build `?` placeholders and pass values separately.  
**Tests:** All 46 existing tests pass. A regression test for special characters in
project names is recommended before v1 tag.