#!/usr/bin/env bash
# rabbit_workflow_hygiene.sh — confirmed GitButler workspace cleanup (GH-320).
#
# Reads .rabbit-loop/preflight.json (from rabbit_workflow_context.sh) and optionally
# unapplies dead lanes, runs but clean, then but pull. Never mutates without --apply.
#
# Usage:
#   scripts/rabbit_workflow_hygiene.sh --dry-run
#   scripts/rabbit_workflow_hygiene.sh --apply
#
# Exit: 0 = done or dry-run listed actions, 2 = setup/refuse
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "rabbit_workflow_hygiene: not inside a git repository" >&2
  exit 2
}
cd "$REPO_ROOT"

APPLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) APPLY=0; shift ;;
    --apply) APPLY=1; shift ;;
    -h|--help)
      awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"
      exit 0
      ;;
    *) echo "rabbit_workflow_hygiene: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

PREFLIGHT="$REPO_ROOT/.rabbit-loop/preflight.json"
[[ -f "$PREFLIGHT" ]] || {
  echo "rabbit_workflow_hygiene: missing $PREFLIGHT — run scripts/rabbit_workflow_context.sh first." >&2
  exit 2
}

command -v but >/dev/null 2>&1 || {
  echo "rabbit_workflow_hygiene: but CLI not found." >&2
  exit 2
}

CURRENT="$(git branch --show-current 2>/dev/null || echo "")"
[[ "$CURRENT" == gitbutler/* ]] || {
  echo "rabbit_workflow_hygiene: only for GitButler workspace (on $CURRENT)." >&2
  exit 2
}

readarray -t DEAD_BRANCHES < <(python3 - "$PREFLIGHT" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
for lane in data.get("gitbutler_sync", {}).get("dead_lanes", []):
    br = lane.get("branch", "")
    if br:
        print(br)
PY
)

OPEN_HEADS="$(gh pr list --state open --limit 50 --json headRefName -q '.[].headRefName' 2>/dev/null || true)"

ACTIONS=()
for br in "${DEAD_BRANCHES[@]}"; do
  [[ -z "$br" ]] && continue
  if printf '%s\n' "$OPEN_HEADS" | grep -qxF "$br"; then
    echo "rabbit_workflow_hygiene: refuse — $br still has OPEN PR (fail-closed)." >&2
    exit 2
  fi
  ACTIONS+=("but unapply $br")
done
ACTIONS+=("but clean")
ACTIONS+=("but pull")

if [[ $APPLY -eq 0 ]]; then
  echo "rabbit_workflow_hygiene: dry-run (pass --apply to execute)"
  for a in "${ACTIONS[@]}"; do
    echo "  would: $a"
  done
  exit 0
fi

for a in "${ACTIONS[@]}"; do
  echo "rabbit_workflow_hygiene: $a"
  # shellcheck disable=SC2086
  $a
done
echo "rabbit_workflow_hygiene: done — re-run scripts/rabbit_workflow_context.sh"
