# Decision: CLI UX guidelines v1

Status: Active  
Date: 2026-04-16  
Owner: Maintainer + active agent

## Why

Recent UX work added command-specific heroes and safer onboarding language, but
the style drifted between commands before a shared guideline existed.

This document defines a lightweight baseline so future UX changes stay
consistent from the start.

## Command hero system

For key commands (`status`, `doctor`, `setup`, `setup-global-timelog`, `report`):

- render a command-specific hero at command start,
- keep one visual frame style across commands,
- keep copy to 3-4 short lines max,
- include one concrete tip line,
- include one safety/quality reminder line.

Use `outputs/cli_heroes.py` as the single source of hero variants.

## Color and table consistency

For setup/doctor/status terminal tables:

- use `ROUNDED` box style,
- use shared terminal theme tokens from `outputs/terminal_theme.py`,
- avoid ad-hoc inline colors when a shared token exists.

## Copy tone

- direct, calm, and action-oriented,
- avoid long paragraphs before first interaction,
- prefer "what happens next" phrasing over internal implementation wording.

## Mascot expression policy (cat/rabbit)

Use mascot expression to signal command mode with low cognitive cost:

- **First-meeting / welcome moments** (`setup` start): slightly cuter and warmer.
- **Work mode commands** (`status`, `report`): neutral and focused.
- **Troubleshooting mode** (`doctor`): alert expression (for example wider eyes)
  to signal active diagnosis.

Keep variation subtle:

- vary eyes for mode switching first,
- vary mouth sparingly to avoid visual noise,
- keep ASCII shape stable so it still feels like one product family.

## UX testing expectations

Every CLI UX batch should include tests that verify:

1. key commands still execute in dry-run/smoke paths,
2. hero sections render for supported commands,
3. no Unicode drift in terminal surfaces where ASCII is expected.

Minimum commands covered in regression tests:

- `setup --yes --dry-run --skip-smoke`
- `setup-global-timelog --yes --dry-run`
- `doctor --github-source auto`
- `status --today`
- `report --today --source-summary --quiet`
- `ux-heroes`

