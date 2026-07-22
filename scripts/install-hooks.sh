#!/bin/sh
# Installs git hooks:
#   - pre-push:   runs the full test suite before any push.
#   - pre-commit: blocks real client/customer data from committed docs (#429).
# Safe to re-run; will not overwrite a hook that already has custom content.
# Usage: bash scripts/install-hooks.sh

set -e

if [ ! -d ".git" ]; then
  echo "Error: must be run from the repo root (no .git directory found)." >&2
  exit 1
fi

# Honour a custom core.hooksPath (this machine sets one for global-timelog).
HOOK_DIR="$(git config core.hooksPath 2>/dev/null || true)"
[ -n "$HOOK_DIR" ] || HOOK_DIR=".git/hooks"
mkdir -p "$HOOK_DIR"

install_hook() {
  name="$1"; body="$2"; path="$HOOK_DIR/$name"
  if [ -f "$path" ] && ! grep -q "install-hooks.sh" "$path"; then
    echo "Warning: $path exists with custom content. Not overwriting."
    echo "To install manually, add this to $path:"
    printf '%s\n' "$body"
    return 0
  fi
  printf '%s' "$body" > "$path"
  chmod +x "$path"
  echo "Installed $name hook at $path"
}

install_hook "pre-push" '#!/bin/sh
# Auto-installed by scripts/install-hooks.sh
echo "[pre-push] Running test suite..."
bash scripts/run_autotests.sh || { echo "[pre-push] Tests failed — push blocked."; exit 1; }
'

install_hook "pre-commit" '#!/bin/sh
# Auto-installed by scripts/install-hooks.sh — block client data in docs (#429).
# Runs from the repo the commit targets; reads client terms from local config.
root="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
if [ -f "$root/scripts/check_docs_no_client_data.py" ]; then
  python3 "$root/scripts/check_docs_no_client_data.py" --staged || {
    echo "[pre-commit] Client data in staged docs — commit blocked (#429)."; exit 1; }
fi
'

echo "Done. 'git push' runs autotests; 'git commit' scans staged docs for client data."
