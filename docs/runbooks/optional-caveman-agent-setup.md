# Optional: Caveman-style agent compression (local only)

This repository does **not** require [Caveman](https://github.com/juliusbrussee/caveman). It is **optional** tooling for developers who want shorter agent replies and lower output-token use in private sessions.

## What it is

Upstream describes a skill/ruleset that nudges coding agents toward more compressed prose (fewer filler words) while keeping technical content. Installation and file layout **change over time** — always read the project `README.md` on GitHub for current steps.

## Install (follow upstream)

1. Open [juliusbrussee/caveman](https://github.com/juliusbrussee/caveman).
2. Use whatever install path the README documents (for example `npx`-based skill install or manual copy of rule files).
3. Keep changes **local** or in a **personal gitignored** config unless the team explicitly agrees to commit shared rules.

## When **not** to use it

Turn off or use normal tone when writing anything **maintainer- or reviewer-facing**:

- GitHub **PR titles and descriptions** (this project expects **English**, complete sentences — see `AGENTS.md`).
- **Release notes**, **changelog** user-facing copy, and **sponsor-facing** text.
- Any situation where brevity would hide safety, ambiguity, or decision rationale.

Caveman is for **speed in the inner loop**, not for **external communication quality**.

## Cursor vs other agents

Caveman is **not** a Cursor product. It is a **third-party** skill that may ship adapter files for several agents (Cursor, Claude Code, and others depending on upstream). Cursor’s own knobs are **Rules** (`.cursor/rules/`), **Skills** (including user-level skills), and **MCP** — there is no single vendor “Caveman” feature inside Cursor itself.

## “Standard”?

There is **no single de-facto industry standard** yet for “skills” across IDEs: naming, install paths, and packaging differ (Anthropic skills, Cursor skills, `npx` skill installers, etc.). Treat Caveman as **one optional pattern**, not a requirement for this repo.
