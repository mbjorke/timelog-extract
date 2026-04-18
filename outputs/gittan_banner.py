"""ASCII banner for CLI reports — original art, not third-party logos.

Raster brand assets (favicon, README icon, ``gittan-logo.png`` for the site, OG image)
are derived from canonical ``docs/brand/gittan-brand-mark.png`` / ``gittan-og-card.png``;
see ``docs/brand/identity.md`` and ``scripts/build_brand_assets.sh``.
"""

from __future__ import annotations

# Compact framed hero to mirror modern CLI onboarding style.
# ASCII letters/symbols only (see tests/test_i18n_only_english.py).
# Metaphor: bumblebee pollinating berries (see docs/brand/identity.md).
GITTAN_BUMBLEBEE_BERRIES = r"""
+-------------------------------------------------------------------------+
|    __      Gittan CLI                                                   |
|   /oo\     Choose timeframe to get started.                             |
|   \__/     Tip: run `gittan status --today` for a fast check.           |
|  o    o    Verify AI-assisted estimates before reporting/invoicing.     |
+-------------------------------------------------------------------------+
""".strip(
    "\n"
)

TAGLINE = "Local timeline -> review-ready."


def banner_panel_lines() -> list[str]:
    """Lines for Rich Panel / Text (no trailing empty noise)."""
    lines = [ln.rstrip() for ln in GITTAN_BUMBLEBEE_BERRIES.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines
