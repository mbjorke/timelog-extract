#!/usr/bin/env bash
# Regenerate all brand assets from canonical SVG sources in docs/brand/marks/.
#
# Usage:
#   ./scripts/build_brand_assets.sh
#
# Requires: rsvg-convert (librsvg) + magick (ImageMagick 7+)
#   brew install librsvg imagemagick
#
# Outputs (repo root):
#   favicon.svg, favicon.ico, favicon-16x16.png, favicon-32x32.png,
#   apple-touch-icon.png, android-chrome-192x192.png, android-chrome-512x512.png,
#   og-image.png, twitter-card.png, gittan-readme-icon.png, site.webmanifest
#
# Legacy PNG masters (docs/brand/gittan-brand-mark.png) are preserved as fallback
# when SVG sources are not yet present.
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MARKS_DIR="docs/brand/marks"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ── SVG path (canonical) ──────────────────────────────────────────────────────
SVG_SOURCES=("bee.svg" "touch-icon.svg" "og-image.svg")
svg_ready=true
for svg in "${SVG_SOURCES[@]}"; do
  [[ -f "$MARKS_DIR/$svg" ]] || svg_ready=false
done

if $svg_ready && command -v rsvg-convert >/dev/null 2>&1; then

  echo "Building from SVG sources ($MARKS_DIR/)…"

  # favicon.svg — Bee mark, used directly by modern browsers
  cp "$MARKS_DIR/bee.svg" favicon.svg

  # favicon.ico — Bee only, rendered at 1.25× then center-cropped so it fills the frame.
  for pair in "20:16" "40:32" "60:48"; do
    IFS=":" read -r render_px target_px <<< "$pair"
    rsvg-convert -w "$render_px" -h "$render_px" "$MARKS_DIR/bee.svg" \
      | magick - -gravity center -background "#0c1119" -extent "${target_px}x${target_px}" "$TMP/fav-${target_px}.png"
  done
  magick "$TMP/fav-16.png" "$TMP/fav-32.png" "$TMP/fav-48.png" favicon.ico

  cp "$TMP/fav-16.png" favicon-16x16.png
  cp "$TMP/fav-32.png" favicon-32x32.png

  # README icon (128×128 square, dark bg)
  rsvg-convert -w 128 -h 128 "$MARKS_DIR/touch-icon.svg" > gittan-readme-icon.png

  # Apple touch icon — 180×180
  rsvg-convert -w 180 -h 180 "$MARKS_DIR/touch-icon.svg" > apple-touch-icon.png

  # Android / PWA icons
  rsvg-convert -w 192 -h 192 "$MARKS_DIR/touch-icon.svg" > android-chrome-192x192.png
  rsvg-convert -w 512 -h 512 "$MARKS_DIR/touch-icon.svg" > android-chrome-512x512.png

  # OG image + Twitter card — 1200×630
  rsvg-convert -w 1200 -h 630 "$MARKS_DIR/og-image.svg" > og-image.png
  cp og-image.png twitter-card.png

  # site.webmanifest
  cat > site.webmanifest << 'MANIFEST'
{
  "name": "Gittan",
  "short_name": "Gittan",
  "description": "Local-first time logging for AI-era teams",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0c1119",
  "theme_color": "#0c1119",
  "icons": [
    { "src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable" }
  ]
}
MANIFEST

  echo "OK (SVG): favicon.svg/ico, favicon-16/32, apple-touch-icon, android-chrome-192/512, og-image, twitter-card, gittan-readme-icon, site.webmanifest"

# ── PNG fallback (legacy masters) ────────────────────────────────────────────
else
  MARK="docs/brand/gittan-brand-mark.png"
  OG_SRC="docs/brand/gittan-og-card.png"
  FILTER="${BRAND_RESIZE_FILTER:-point}"
  LOGO_SIZE="${BRAND_LOGO_PX:-768}"

  if [[ ! -f "$MARK" ]]; then
    echo "error: $MARKS_DIR/blueberry.svg not found (rsvg-convert missing?) and $MARK also missing." >&2
    echo "  Install rsvg-convert: brew install librsvg" >&2
    exit 1
  fi

  echo "warn: rsvg-convert not found or SVG sources missing — falling back to PNG masters" >&2

  if command -v magick >/dev/null 2>&1; then
    H="$(magick identify -format %h "$MARK" 2>/dev/null)"
    if [[ -z "$H" ]]; then
      echo "error: failed to read image dimensions from $MARK" >&2
      exit 1
    fi
    SQ="$(mktemp -t gittan-brand-sq.XXXXXX.png)"
    magick "$MARK" -gravity center -extent "${H}x${H}" -filter "$FILTER" "$SQ"
    magick "$SQ" -define icon:auto-resize=16,32,48,64 favicon.ico
    magick "$SQ" -filter "$FILTER" -resize '16x16'          favicon-16x16.png
    magick "$SQ" -filter "$FILTER" -resize '32x32'          favicon-32x32.png
    magick "$SQ" -filter "$FILTER" -resize '128x128'        gittan-readme-icon.png
    magick "$SQ" -filter "$FILTER" -resize "${LOGO_SIZE}x${LOGO_SIZE}" gittan-logo.png
    rm -f "$SQ"
  else
    python3 - <<PY
from pathlib import Path
from PIL import Image
im = Image.open(Path("$MARK")).convert("RGBA")
w, h = im.size
side = min(w, h)
sq = im.crop(((w-side)//2, (h-side)//2, (w+side)//2, (h+side)//2))
sq.save(Path("favicon.ico"), format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64)])
sq.resize((16,16),  Image.Resampling.NEAREST).save(Path("favicon-16x16.png"))
sq.resize((32,32),  Image.Resampling.NEAREST).save(Path("favicon-32x32.png"))
sq.resize((128,128),Image.Resampling.NEAREST).save(Path("gittan-readme-icon.png"))
sq.resize((int("$LOGO_SIZE"),int("$LOGO_SIZE")),Image.Resampling.NEAREST).save(Path("gittan-logo.png"))
PY
  fi

  [[ -f "$OG_SRC" ]] && cp "$OG_SRC" og-image.png
  echo "OK (PNG fallback): favicon.ico, favicon-16/32, gittan-readme-icon, gittan-logo"
fi
