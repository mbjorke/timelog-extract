#!/usr/bin/env bash
# rabbit_board_sync.sh — add/update the current branch's open PR on the project board.
#
# Part of the kanin-loop board flow: PRs must be visible on the board, not only issues.
# Typically called from rabbit_loop.sh on CONVERGED (Status → "In review") or manually
# after `gh pr create`.
#
# Usage:
#   scripts/rabbit_board_sync.sh [--pr N] [--status "In review"]
#                               [--project 3] [--owner mbjorke] [--dry-run]
#
# Default: open PR for the current branch; Status "In review".
# Exit: 0 = synced (or dry-run), 2 = setup/API error, 3 = no open PR found (not an error
#       for pre-PR work — caller may ignore).

set -euo pipefail

PROJECT="3"
OWNER="mbjorke"
STATUS="In review"
PR_NUM=""
PR_EXPLICIT=0
DRY_RUN=0

usage() { awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr)      [[ $# -ge 2 ]] || { echo "rabbit_board_sync: --pr needs a number" >&2; exit 2; }; PR_EXPLICIT=1; PR_NUM="$2"; shift 2 ;;
    --status)  [[ $# -ge 2 ]] || { echo "rabbit_board_sync: --status needs a column name" >&2; exit 2; }; STATUS="$2"; shift 2 ;;
    --project) [[ $# -ge 2 ]] || { echo "rabbit_board_sync: --project needs a number" >&2; exit 2; }; PROJECT="$2"; shift 2 ;;
    --owner)   [[ $# -ge 2 ]] || { echo "rabbit_board_sync: --owner needs a login" >&2; exit 2; }; OWNER="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage ;;
    *) echo "rabbit_board_sync: unknown arg '$1' (try --help)" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "rabbit_board_sync: not inside a git repository" >&2; exit 2; }
cd "$REPO_ROOT"

command -v gh >/dev/null 2>&1 || { echo "rabbit_board_sync: gh CLI not found." >&2; exit 2; }
if ! gh auth status 2>&1 | grep -q "project"; then
  echo "rabbit_board_sync: gh is missing the 'project' scope. Run: gh auth refresh -s project" >&2
  exit 2
fi

BOARD_PY="$REPO_ROOT/scripts/rabbit_board.py"
[[ -f "$BOARD_PY" ]] || { echo "rabbit_board_sync: $BOARD_PY not found." >&2; exit 2; }

if [[ -z "$PR_NUM" ]]; then
  BR="$(git branch --show-current 2>/dev/null || true)"
  [[ -n "$BR" ]] || { echo "rabbit_board_sync: detached HEAD — pass --pr N." >&2; exit 2; }
  PR_JSON="$(gh pr list --head "$BR" --state open --limit 1 --json number,url 2>/dev/null || true)"
  PR_NUM="$(python3 -c "import json,sys; d=json.loads(sys.argv[1] or '[]'); print(d[0]['number'] if d else '')" "$PR_JSON" 2>/dev/null || true)"
  PR_URL="$(python3 -c "import json,sys; d=json.loads(sys.argv[1] or '[]'); print(d[0]['url'] if d else '')" "$PR_JSON" 2>/dev/null || true)"
else
  PR_URL="$(gh pr view "$PR_NUM" --json url --jq '.url' 2>/dev/null || true)"
fi

if [[ -z "${PR_URL:-}" ]]; then
  if [[ $PR_EXPLICIT -eq 1 ]]; then
    echo "rabbit_board_sync: could not resolve PR #$PR_NUM (is it open and does it exist?)." >&2
  else
    echo "rabbit_board_sync: no open PR for this branch (pass --pr N after gh pr create)." >&2
  fi
  exit 3
fi

ARGS=(python3 "$BOARD_PY" --owner "$OWNER" --project "$PROJECT" --url "$PR_URL" --status "$STATUS")
[[ $DRY_RUN -eq 1 ]] && ARGS+=(--dry-run)

set +e
OUT="$("${ARGS[@]}" 2>&1)"
RC=$?
set -e
if [[ $RC -ne 0 ]]; then
  echo "$OUT" >&2
  exit 2
fi

if [[ $DRY_RUN -eq 1 ]]; then
  echo "rabbit_board_sync: DRY RUN — would set PR #$PR_NUM → Status '$STATUS' ($OUT)"
else
  echo "rabbit_board_sync: PR #$PR_NUM → board Status '$STATUS' (item $OUT)"
fi
exit 0
