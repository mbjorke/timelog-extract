# Changelog + beta distribution — draft plan

Status: **draft / not decided** (2026-08-24).  
Benchmark: [Comms changelog](https://trycomms.app/changelog) (human headlines, version anchors, New/Fixed/Improved).

Cross-repo surfaces this touches:

| Repo | Role |
| --- | --- |
| **`timelog-extract`** (PyPI `gittan`) | Engine + CLI; canonical `CHANGELOG.md`; PyPI + GitHub Releases |
| **`gittan-home`** (`gittan.sh`) | Marketing site, `install` script, beta copy — **no changelog page today** |
| **`briox-buddy`** (private GUI) | Web + Electron shell; consumes CLI truth payload locally |

Related existing docs: [`specs/gittan-web-surface-architecture.md`](../specs/gittan-web-surface-architecture.md), [`runbooks/homebrew-tap.md`](../runbooks/homebrew-tap.md), [`runbooks/beta-onboarding-config.md`](../runbooks/beta-onboarding-config.md), [`ideas/simple-invoicing-model.md`](simple-invoicing-model.md).

## Problem

- Maintainers have **`CHANGELOG.md`** (Keep a Changelog, technical) + `scripts/changelog_section.py` for GitHub Release bodies.
- Public site has **install + beta status** but no **versioned, linkable release notes** like Comms (`/changelog#v0.6.4`).
- GUI consumer exists (`briox-buddy` + Electron scaffold); distribution shape for beta testers is **not decided**.

## Comms pattern to borrow

Per release:

1. **Version + date** with hash anchor (`#0.5.0`).
2. **One human headline** (“Review-ready without YAML marathon”) — not just semver.
3. Bullets grouped **New / Fixed / Improved** in plain language.
4. Optional: beta expiry, feedback link, download CTA.

Not copying: Comms is a signed macOS app with auto-update; Gittan is CLI-first and local-first.

## Two-layer changelog (proposal)

| Layer | Audience | Source | Where it lives |
| --- | --- | --- | --- |
| **Maintainer** | Contributors, GitHub | `CHANGELOG.md` in `timelog-extract` | Repo root; drives PyPI/GitHub Release via `changelog_section.py` |
| **Public** | Beta users, design partners | Curated subset (manual or semi-automated) | `gittan.sh/changelog` — e.g. `gittan-home/data/changelog.json` or markdown fragments |

Public entries need not mirror every patch release; ship when there is something a beta user should **do** (upgrade, re-run setup, new command).

## Downloadable beta vs cloud (proposal)

**Default: downloadable / local-first — not a Gittan-operated cloud product.**

| Surface | Today | Beta path |
| --- | --- | --- |
| **CLI** | Already downloadable: PyPI + `curl \| bash` on `gittan.sh/install` | Pin with `--version`; link latest from changelog |
| **GUI** | `briox-buddy`: Vite web app + `desktop-shell/` (Electron) | **Phase 1:** browser + local JSON export. **Phase 2:** `.dmg` on GitHub Releases / gittan.sh — same UI, no server |
| **Demo API** | `api.gittan.sh` | Marketing mock only — **not** product engine ([architecture spec](../specs/gittan-web-surface-architecture.md)) |

**Cloud SaaS** (hosted accounts, synced evidence, web-as-source-of-truth) conflicts with [`decisions/private-not-local.md`](../decisions/private-not-local.md) and retired Freelance Bridge shape. Revisit only for **optional push** (Toggl/Jira/Briox draft export), not as the reporting engine.

**Why downloadable is easier now:** engine already runs locally; GUI adapter loads JSON from `gittan report --format json`; Electron shell exists (`npm run desktop:dev`). Cloud would require auth, storage, sync, and a second classifier — high cost, low fit.

## Open decisions (not made)

1. **Single changelog** for CLI + GUI vs separate tracks (shared brand, different semver?).
2. **Who curates public copy** — hand-written per release vs script from `CHANGELOG.md` + headline field.
3. **GUI beta gate** — ship Electron before or after pilot-workflows gate in **briox-buddy** (private GUI repo).
4. **Where to host GUI artifacts** — GitHub Releases vs R2 on gittan.sh vs both.
5. **Auto-update** — defer (Sparkle/etc.) until after first manual beta wave.

## Suggested next steps (when we pick this up)

1. Add `gittan-home/changelog` page + one entry for current PyPI version (prove the format).
2. Link footer + beta section on gittan.sh → `/changelog`.
3. Document GUI beta as “download .dmg” in same changelog entry when Electron packaging lands.
4. Promote to `docs/specs/` + `docs/decisions/` once distribution choice is explicit.

## Explicit non-goals (for now)

- Building Gittan Cloud as primary beta delivery.
- Replacing `CHANGELOG.md` — public layer sits on top.
- Committing implementation in `gittan-home` or `briox-buddy` in this doc alone.
