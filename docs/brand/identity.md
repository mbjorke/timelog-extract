# Gittan visual identity (living notes)

Evolves with the product. **ASCII spirit:** `outputs/gittan_banner.py` (`GITTAN_FEEDING_RABBIT`, `TAGLINE`).

## What works today

- **Raster marks:** `gittan-brand-mark.png` + `gittan-og-card.png` — the **rabbit-in-terminal-frame** campaign (also kept as identical copies in `archive/*-rabbit-v2.png` for safety). No need to force extra metaphors (steward, victuals, “rabbit as dinner”) into the art unless you *want* to explore that later.
- **Review rabbit** — lives in **terminal copy** and mascot energy: good traces make reviews easier. The **logo** can stay a friendly rabbit + frame + timeline without illustrating every joke literally.
- **Terminal frame** — L-shaped corners echo the banner’s `.----------.` panel; palette matches the site (void `#0a0714`, berry `#a855f7`, rose `#ec4899`, cream `#f0ebff`, terminal green `#34d399` / amber `#f5a623`).

## What Gittan is (short)

**Gittan** shapes **local activity → review-ready** output. **You** do the work; **traces** are the raw material. The rabbit in the banner is **who benefits** when that output is clear — tool, teammate, or future you.

## Files

- **Canonical:** `gittan-brand-mark.png`, `gittan-og-card.png` → run `scripts/build_brand_assets.sh` for favicon / README icon / root `og-image.png`.
- **Site logo:** root **`gittan-logo.png`** (generated, square crop from the mark, default 768px, pixel-crisp) — **`gittan.html`** + Pages; rebuild with `scripts/build_brand_assets.sh`.
- **Archive:** duplicate **rabbit-v2** snapshots — backup only.
- **Drafts:** optional experiments; promote by copying over the canonical PNGs when ready.