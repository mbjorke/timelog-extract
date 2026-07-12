## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-12 - Standardized 'sources' analysis UX
**Learning:** Dense data tables (like source importance analysis) become much more trustworthy when they share the same 'light grid' and border semantics as the rest of the CLI. Using color tokens for semantics (blue for source, orange for impact) rather than ad-hoc colors makes the output feel like a coherent product.
**Action:** Aligned 'sources' command table with STYLE_BORDER and STYLE_LABEL. Replaced ad-hoc Rich colors with theme tokens. Added conditional "Next:" guidance based on uncategorized signal hits.
