#!/bin/sh
# Installs a pre-push git hook that runs the full test suite before any push.
# Safe to re-run; will not overwrite a hook that already has custom content.
# Usage: bash scripts/install-hooks.sh

set -e

HOOK=".git/hooks/pre-push"
CONTENT='#!/bin/sh
# Auto-installed by scripts/install-hooks.sh
echo "[pre-push] Running test suite..."
bash scripts/run_autotests.sh || { echo "[pre-push] Tests failed — push blocked."; exit 1; }
'

if [ ! -d ".git" ]; then
  echo "Error: must be run from the repo root (no .git directory found)." >&2
  exit 1
fi

mkdir -p .git/hooks

if [ -f "$HOOK" ] && ! grep -q "install-hooks.sh" "$HOOK"; then
  echo "Warning: $HOOK already exists with custom content. Not overwriting."
  echo "To install manually, add this to $HOOK:"
  printf '%s\n' "$CONTENT"
  exit 0
fi

printf '%s' "$CONTENT" > "$HOOK"
chmod +x "$HOOK"
echo "Installed pre-push hook at $HOOK"
echo "Every 'git push' will now run 'bash scripts/run_autotests.sh' automatically."
