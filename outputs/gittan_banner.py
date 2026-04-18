"""ASCII banner for CLI reports — original art, not third-party logos.

Raster brand assets (favicon, README icon, ``gittan-logo.png`` for the site, OG image)
are derived from canonical ``docs/brand/gittan-brand-mark.png`` / ``gittan-og-card.png``;
see ``docs/brand/identity.md`` and ``scripts/build_brand_assets.sh``.
"""

from __future__ import annotations

# Compact framed hero to mirror modern CLI onboarding style.
# ASCII letters/symbols only (see tests/test_i18n_only_english.py).
GITTAN_FEEDING_RABBIT = r"""
+-------------------------------------------------------------------------+
|  /\_/\   Gittan CLI                                                     |
| ( o.o )  Choose timeframe to get started.                               |
|  > ^ <   Tip: run `gittan status --today` for a fast check.             |
|          AI-assisted estimates: always verify before reporting/invoicing.|
+-------------------------------------------------------------------------+
""".strip(
    "\n"
)

TAGLINE = "Local timeline -> review-ready."


def banner_panel_lines() -> list[str]:
    """Lines for Rich Panel / Text (no trailing empty noise)."""
    lines = [ln.rstrip() for ln in GITTAN_FEEDING_RABBIT.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines
