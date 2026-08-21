#!/bin/sh
# Installs git hooks:
#   - pre-push:   runs the full test suite before any push.
#   - pre-commit: blocks real client/customer data from committed docs (#429).
# Safe to re-run; will not overwrite a hook that already has custom content.
# Usage: bash scripts/install-hooks.sh

set -e

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: must be run inside the git repository." >&2
  exit 1
fi

# Honour a custom core.hooksPath (this machine sets one for global-timelog);
# otherwise resolve the real hooks dir via git so linked worktrees work
# (where .git is a file pointing at the gitdir, not a directory).
HOOK_DIR="$(git config core.hooksPath 2>/dev/null || true)"
[ -n "$HOOK_DIR" ] || HOOK_DIR="$(git rev-parse --git-path hooks 2>/dev/null || echo .git/hooks)"
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
# Guarded by a repo-identity check: this machine may set a *global* core.hooksPath,
# so the hook also runs for unrelated repositories. Without any guard, a repo
# with no run_autotests.sh makes bash exit 127 and blocks every push there.
# A path-only check is still too broad: other projects also ship
# scripts/run_autotests.sh. Require the timelog-extract entry module too,
# so the suite runs only inside this repo and no-ops everywhere else.
root="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
if [ -f "$root/scripts/run_autotests.sh" ] && [ -f "$root/timelog_extract.py" ]; then
  echo "[pre-push] Running test suite..."
  # git exports GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE into hook environments.
  # The suite shells out to git in temporary repositories, so those inherited
  # values point every child git call at the pushing repository and the run
  # fails with dozens of unrelated errors. Clear them before running.
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_QUARANTINE_PATH
  bash "$root/scripts/run_autotests.sh" || { echo "[pre-push] Tests failed — push blocked."; exit 1; }
fi
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
