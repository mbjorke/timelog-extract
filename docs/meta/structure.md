# Repository Structure

Status: active  
Owner: Maintainer + active implementation agent

For **where to place markdown under `docs/`** (taxonomy and routing), see [`../README.md`](../README.md).

## Goals

- keep domain code grouped by bounded context
- keep script entrypoints grouped by intent (`ci`, `calibration`, later `release`)
- normalize documentation filenames toward lowercase-kebab-case
- preserve compatibility during transitions with explicit wrappers

## Current structure decisions

- `core/calibration/` owns experiment, reconciliation, and screen-time calibration logic
- `core/live_terminal/` owns live-terminal contract + runtime sketch code
- `scripts/ci/` hosts CI-focused script entrypoints
- `scripts/calibration/` hosts calibration/reconciliation report scripts
- legacy root-level script paths remain as wrappers for backward compatibility

## Filename convention for docs

Default for new docs:

- lowercase-kebab-case filenames (example: `release-readiness-checklist.md`)
- keep repo-standard special files unchanged when required by tooling (`README.md`, `CHANGELOG.md`, `AGENTS.md`, `CLAUDE.md`)

Migration policy:

- move high-traffic docs first and update links in the same change
- keep risk low by combining rename + reference updates per batch
- avoid partial renames that leave broken references