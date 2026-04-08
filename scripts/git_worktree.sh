#!/usr/bin/env bash
# Add / list / remove git worktrees for this repo from a predictable sibling path.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/git_worktree.sh add <branch> [dir-name]
      Creates a sibling worktree ../<dir-name>.
      Default dir-name: <repo-basename>--<branch> (slashes → hyphens).
      If <branch> exists locally, checks it out; otherwise creates it with -b.
  scripts/git_worktree.sh list
      Same as: git worktree list
  scripts/git_worktree.sh remove <path-or-basename>
      Removes a worktree. Pass absolute path, or just the directory name next to the main repo.

Examples (run from main clone):
  scripts/git_worktree.sh add idea/pdf-footer
  scripts/git_worktree.sh add review/cr-3 timelog-extract--review-cr-3
EOF
  exit 2
}

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Not inside a git repository." >&2
  exit 1
}
cd "$REPO_ROOT"

REPO_BASENAME="$(basename "$REPO_ROOT")"
PARENT="$(dirname "$REPO_ROOT")"

slug_branch() {
  local b="$1"
  b="${b//\//-}"
  b="${b// /-}"
  printf '%s' "$b"
}

cmd_add() {
  local branch="${1:?branch name required}"
  local dir_name="${2:-}"
  local slug
  slug="$(slug_branch "$branch")"
  if [[ -z "$dir_name" ]]; then
    dir_name="${REPO_BASENAME}--${slug}"
  fi
  local wt_path="$PARENT/$dir_name"
  if [[ -e "$wt_path" ]]; then
    echo "Refusing to clobber existing path: $wt_path" >&2
    exit 1
  fi
  if git show-ref --verify --quiet "refs/heads/$branch"; then
    git worktree add "$wt_path" "$branch"
  else
    git worktree add -b "$branch" "$wt_path"
  fi
  echo ""
  echo "Worktree ready: $wt_path"
  echo "Open in Cursor: File → Open Folder… → $wt_path"
}

cmd_list() {
  git worktree list
}

cmd_remove() {
  local target="${1:?path or directory name required}"
  local wt_path
  if [[ "$target" = /* ]]; then
    wt_path="$target"
  elif [[ "$target" == */* ]]; then
    wt_path="$(cd "$(dirname "$target")" && pwd)/$(basename "$target")"
  else
    wt_path="$PARENT/$target"
  fi
  git worktree remove "$wt_path"
}

case "${1:-}" in
add) shift && cmd_add "$@" ;;
list) cmd_list ;;
remove) shift && cmd_remove "$@" ;;
-h | --help | help) usage ;;
*) usage ;;
esac
