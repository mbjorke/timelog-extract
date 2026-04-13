#!/usr/bin/env bash
# Build _site/ for GitHub Pages (landing + static assets). Used by CI verify and deploy.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p _site
if [ ! -f "gittan.html" ]; then
  echo "No landing page file found (expected gittan.html)." >&2
  exit 1
fi
cp "gittan.html" _site/index.html
if [ -f "favicon.ico" ]; then
  cp "favicon.ico" _site/favicon.ico
fi
if [ -f "og-image.png" ]; then
  cp "og-image.png" _site/og-image.png
fi
if [ -f "gittan-logo.png" ]; then
  cp "gittan-logo.png" _site/gittan-logo.png
fi
if [ -f CNAME ]; then
  cp CNAME _site/CNAME
fi
test -f _site/index.html
