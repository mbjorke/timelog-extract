#!/usr/bin/env bash
# rabbit_workflow_hygiene.sh — confirmed GitButler workspace cleanup (GH-320).
#
# Reads .rabbit-loop/preflight.json (from rabbit_workflow_context.sh) and optionally
# unapplies dead lanes, runs but clean, then but pull. Never mutates without --apply.
#
# Usage:
#   scripts/rabbit_workflow_hygiene.sh --dry-run
#   scripts/rabbit_workflow_hygiene.sh --apply
#   scripts/rabbit_workflow_hygiene.sh --dry-run --preflight /path/to/preflight.json
#
# Exit: 0 = done or dry-run listed actions, 2 = setup/refuse
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "rabbit_workflow_hygiene: not inside a git repository" >&2
  exit 2
}
cd "$REPO_ROOT"

APPLY=0
PREFLIGHT_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) APPLY=0; shift ;;
    --apply) APPLY=1; shift ;;
    --preflight)
      PREFLIGHT_OVERRIDE="${2:?--preflight needs a path}"
      shift 2
      ;;
    -h|--help)
      awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"
      exit 0
      ;;
    *) echo "rabbit_workflow_hygiene: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

PREFLIGHT="${PREFLIGHT_OVERRIDE:-$REPO_ROOT/.rabbit-loop/preflight.json}"
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

command -v gh >/dev/null 2>&1 || {
  echo "rabbit_workflow_hygiene: gh CLI required for fail-closed PR checks." >&2
  exit 2
}
if ! gh auth status >/dev/null 2>&1; then
  echo "rabbit_workflow_hygiene: gh not authenticated — refusing hygiene (fail-closed)." >&2
  exit 2
fi

_lane_has_open_pr() {
  local br="$1"
  local out count
  out="$(gh pr list --head "$br" --state open --limit 1 --json number 2>&1)" || {
    echo "rabbit_workflow_hygiene: gh pr list failed for $br — refusing (fail-closed)." >&2
    echo "$out" >&2
    return 1
  }
  count="$(printf '%s' "$out" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')"
  [[ "$count" == "0" ]]
}

_lane_has_unpushed_commits() {
  local br="$1"
  if ! git show-ref --verify --quiet "refs/heads/$br"; then
    echo "rabbit_workflow_hygiene: refuse — cannot resolve refs/heads/$br (fail-closed)." >&2
    return 0
  fi
  local upstream ahead
  upstream="$(git rev-parse --abbrev-ref "$br@{upstream}" 2>/dev/null || true)"
  if [[ -n "$upstream" ]]; then
    ahead="$(git rev-list --left-right --count "${upstream}...${br}" 2>/dev/null | awk '{print $2}')"
    if [[ "${ahead:-0}" -gt 0 ]]; then
      echo "rabbit_workflow_hygiene: refuse — $br has ${ahead} unpushed commit(s) on $upstream." >&2
      return 0
    fi
    return 1
  fi
  if git show-ref --verify --quiet "refs/remotes/origin/$br"; then
    ahead="$(git rev-list --count "origin/$br..$br" 2>/dev/null || echo 0)"
    if [[ "${ahead:-0}" -gt 0 ]]; then
      echo "rabbit_workflow_hygiene: refuse — $br has ${ahead} unpushed commit(s) vs origin/$br." >&2
      return 0
    fi
    return 1
  fi
  ahead="$(git rev-list --count "origin/main..$br" 2>/dev/null || echo 0)"
  if [[ "${ahead:-0}" -gt 0 ]]; then
    echo "rabbit_workflow_hygiene: refuse — $br has no upstream/origin ref but ${ahead} commit(s) ahead of origin/main (fail-closed)." >&2
    return 0
  fi
  return 1
}

ACTIONS=()
DEAD_LANES="$(
  python3 - "$PREFLIGHT" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
for lane in data.get("gitbutler_sync", {}).get("dead_lanes", []):
    br = lane.get("branch", "")
    if br:
        print(br)
PY
)" || {
  echo "rabbit_workflow_hygiene: failed to parse $PREFLIGHT — refusing (fail-closed)." >&2
  exit 2
}
while IFS= read -r br; do
  [[ -z "$br" ]] && continue
  if ! _lane_has_open_pr "$br"; then
    echo "rabbit_workflow_hygiene: refuse — $br still has an OPEN PR (fail-closed)." >&2
    exit 2
  fi
  if _lane_has_unpushed_commits "$br"; then
    exit 2
  fi
  ACTIONS+=("but unapply $br")
done <<< "$DEAD_LANES"

ACTIONS+=("but clean")
ACTIONS+=("but pull")

if [[ $APPLY -eq 0 ]]; then
  echo "rabbit_workflow_hygiene: dry-run (pass --apply to execute)"
  idx=0
  while [[ $idx -lt ${#ACTIONS[@]} ]]; do
    echo "  would: ${ACTIONS[$idx]}"
    idx=$((idx + 1))
  done
  exit 0
fi

idx=0
while [[ $idx -lt ${#ACTIONS[@]} ]]; do
  a="${ACTIONS[$idx]}"
  echo "rabbit_workflow_hygiene: $a"
  # shellcheck disable=SC2086
  $a
  idx=$((idx + 1))
done
echo "rabbit_workflow_hygiene: done — re-run scripts/rabbit_workflow_context.sh"
