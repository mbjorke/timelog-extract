## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-11 - Empty state unification and next steps
**Learning:** Empty states in CLI commands (like `status` and `report`) were inconsistent in their messaging and actionability. A centralized helper for "Next steps" ensures that users are never at a dead end and get consistent advice regardless of which command they ran.
**Action:** Unified empty state "No events found" messaging across `status` and `report`. Implemented `build_empty_report_next_steps` in `core/onboarding_guidance.py` and improved the ambiguous project filter warning with a concrete next command.
