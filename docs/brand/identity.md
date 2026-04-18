# Gittan visual identity (living notes)

**Values and culture (team + product):** [`values.md`](values.md).

Evolves with the product. **ASCII spirit:** `outputs/gittan_banner.py` (`GITTAN_BUMBLEBEE_BERRIES`, `TAGLINE`).

## Core metaphor

**A bumblebee pollinating berries** — local activity traces are like flowers along a branch; Gittan moves signal between them so **fruit** (review-ready output) can form. The **berry palette** in the UI is part of the story, not decoration for its own sake.

## Palette: Blueberry kinship, Gittan vibrancy

- **Family:** Gittan should **feel related** to [Blueberry Maybe](https://blueberry.ax) and the public face of the company (berry violets, deep void, warm accents). **Gittan does not need pixel-perfect parity** with blueberry.ax — clarity and energy come first.
- **Canonical void / terminal background:** **`#0a0714`** — this is the **single anchor** for “terminal window” on the site (`gittan.html`) and the mental model for CLI sessions. Do not drift to a different near-black without updating both docs and CSS together.
- **Berry accents (vibrant):** implemented in **`gittan.html` `:root`** and mirrored for Rich in **`outputs/terminal_theme.py`** — saturated fuchsia/violet berries, brighter rose, readable cream text. When you change the web palette, update the CLI tokens in the same PR so reports and marketing still feel like one product.

## Voice (future): “humle-rader” on PRs

Not shipped yet — document intent only.

Some tools leave **playful poetry** on pull requests (e.g. CodeRabbit-style asides). **Gittan’s** future version should be **shorter, simpler, and sweeter**: a **bumblebee** that **buzzes by** with a tiny line about **pollinating traces** — tagging work with care, not showing off vocabulary. Same warmth, **less literary**, more **“aw, thanks for the commits”**.

## What works today

- **Raster marks:** `gittan-brand-mark.png` + `gittan-og-card.png` — still the **canonical masters** until new bumblebee/berry artwork replaces them; then rerun `scripts/build_brand_assets.sh`. **Archive** `archive/*-rabbit-v2.png` keeps older rabbit-era backups only.
- **Mascot direction** — **bumblebee + berries** in terminal copy and future logo art: friendly, industrious, local motion (pollination), not a literal biology lesson on every screen.
- **Terminal frame** — L-shaped corners echo the banner’s `.----------.` panel; colors follow **`terminal_theme.py`** + site `:root`.

## What Gittan is (short)

**Gittan** shapes **local activity → review-ready** output. **You** do the work; **traces** are the raw material. The bee-and-berries story is **what happens when traces connect** — clearer reports, calmer reviews, future you included.

## Files

- **Canonical:** `gittan-brand-mark.png`, `gittan-og-card.png` → run `scripts/build_brand_assets.sh` for favicon / README icon / root `og-image.png`.
- **Site:** **`gittan.html`** — live CSS variables (void + berry family).
- **CLI colors:** **`outputs/terminal_theme.py`** — keep in sync with `gittan.html`.
- **Site logo:** root **`gittan-logo.png`** (generated, square crop from the mark, default 768px, pixel-crisp) — **`gittan.html`** + Pages; rebuild with `scripts/build_brand_assets.sh`.
- **Archive:** **rabbit-v2** snapshots — historical backup; new era art may add parallel `*-bumblebee-*` masters when ready.
- **Drafts:** optional experiments; promote by copying over the canonical PNGs when ready.
