#!/usr/bin/env bash
# Regenerate favicon, README icon, og-image, and site logo (gittan.html / Pages) from canonical masters.
#
# Usage:
#   ./scripts/build_brand_assets.sh
#
# Outputs (repo root):
#   favicon.ico, gittan-readme-icon.png, og-image.png, gittan-logo.png
#
# Pixel / "taggig" GITTAN: default nearest-neighbor (-filter point / PIL NEAREST).
# Override: BRAND_RESIZE_FILTER=lanczos
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MARK="docs/brand/gittan-brand-mark.png"
OG_SRC="docs/brand/gittan-og-card.png"
FILTER="${BRAND_RESIZE_FILTER:-point}"
LOGO_SIZE="${BRAND_LOGO_PX:-768}"

if [[ ! -f "$MARK" ]]; then
  echo "Missing $MARK — restore from docs/brand/archive/ or add a master." >&2
  exit 1
fi

local_h() {
  if command -v magick >/dev/null 2>&1; then
    magick identify -format %h "$MARK" 2>/dev/null || true
  fi
}

H="$(local_h)"

if command -v magick >/dev/null 2>&1 && [[ -n "${H:-}" ]]; then
  SQ="$(mktemp -t gittan-brand-sq.XXXXXX.png)"
  magick "$MARK" -gravity center -extent "${H}x${H}" -filter "$FILTER" "$SQ"
  magick "$SQ" -define icon:auto-resize=16,32,48,64 favicon.ico
  magick "$SQ" -filter "$FILTER" -resize '128x128' gittan-readme-icon.png
  magick "$SQ" -filter "$FILTER" -resize "${LOGO_SIZE}x${LOGO_SIZE}" gittan-logo.png
  rm -f "$SQ"
else
  echo "warn: ImageMagick (magick) not found; Pillow square-crop + NEAREST" >&2
  python3 - <<PY
from pathlib import Path
from PIL import Image
im = Image.open(Path("$MARK")).convert("RGBA")
w, h = im.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
sq = im.crop((left, top, left + side, top + side))
sq.resize((32, 32), Image.Resampling.NEAREST).save(Path("favicon.ico"), format="ICO")
sq.resize((128, 128), Image.Resampling.NEAREST).save(Path("gittan-readme-icon.png"))
sq.resize((int("$LOGO_SIZE"), int("$LOGO_SIZE")), Image.Resampling.NEAREST).save(Path("gittan-logo.png"))
PY
fi

if [[ -f "$OG_SRC" ]]; then
  cp "$OG_SRC" og-image.png
fi

if [[ -f og-image.png ]]; then
  echo "OK: favicon.ico, gittan-readme-icon.png, gittan-logo.png, og-image.png"
else
  echo "OK: favicon.ico, gittan-readme-icon.png, gittan-logo.png (no $OG_SRC — skipped og-image.png)"
fi
