# AI-assisted project config (vision)

## Intent

A **built-in assistant** (future) should help users create and maintain `timelog_projects.json` without hand-writing every field. This is **not** required for core reporting—the CLI already consumes a normal JSON file—but it lowers friction for onboarding and ongoing edits.

## Phasing (what matters first)

1. **Project names (and rough boundaries)** — get the **right buckets** before tuning keywords. Wrong project split wastes more time than imperfect `match_terms`.
2. **Match terms and optional metadata** — refine classification once names exist (repos, customers, Jira keys, domains).
3. **Optional LLM provider** — opt-in calls using the user’s **API keys** (environment variables), with a **small, explicit** prompt surface (e.g. “here are my project titles, suggest JSON”) rather than sending full activity dumps by default.

Keeping scope tight keeps cost and complexity manageable: **structured output + validation** against the same rules as `core/config.py` (`normalize_profile`).

## Solopreneurs vs Jira-native users

- **Solopreneurs / founders** often need help **inventing** stable project labels and synonyms from messy real-world traces (browser, IDE, ad hoc notes).
- **Teams coming from Jira** (or similar) often already have **project keys, issue prefixes, and board names**—those identifiers map cleanly to **`match_terms`** and can make assistant-driven config **faster and more deterministic** than free-text guessing.

The assistant should not assume one audience: offer **“start from project names”** first, then optional **“import hints from Jira/Linear-style lists”** when the user provides them.

## Safety and privacy

- **Opt-in** for any cloud LLM; local-only workflows remain default.
- **Secrets**: API keys only via **environment** or OS keychain patterns—never committed; document which vars a provider expects.
- **Data minimization**: prefer **metadata the user pastes intentionally** (project list, customer names) over automatic exfiltration of full logs in v1 of the feature.

## Status

**Vision / backlog.** No in-repo assistant ships today; this document aligns product discussion with `docs/GITTAN_VISION.md` and `docs/V1_SCOPE.md`.
