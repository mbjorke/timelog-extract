"""ASCII banner for CLI reports — original art, not third-party logos."""

from __future__ import annotations

# Compact so it fits narrow terminals; ASCII letters/symbols only (see tests/test_i18n_only_english.py).
GITTAN_FEEDING_RABBIT = r"""
   (\/)
   (..)     <- review rabbit
    ><       (well-fed on good traces)
     \
  .----------.
  |  GITTAN  |  local timeline -> review-ready
  '----------'
""".strip(
    "\n"
)

TAGLINE = "Feeds the review rabbit - context beats guessing."


def banner_panel_lines() -> list[str]:
    """Lines for Rich Panel / Text (no trailing empty noise)."""
    lines = [ln.rstrip() for ln in GITTAN_FEEDING_RABBIT.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines
