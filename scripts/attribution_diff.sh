#!/usr/bin/env bash
# attribution_diff.sh — does a code change move the maintainer's real hours?
#
# For any change to the attribution/invoice engine (core/domain.py, aggregation,
# truth_payload), synthetic tests passing is necessary but NOT sufficient: a
# reclassification can silently move billable hours. This runs a report on the
# SAME real window under two git refs and prints the per-project hour delta, so a
# reviewer can judge whether the shift is a correction or a regression.
#
# PRIVACY: the output contains the maintainer's real per-client hours. It is
# printed to your terminal only. NEVER paste it into a GitHub issue/PR/comment —
# describe it in the abstract ("shifts small amounts across a few profiles").
# See AGENTS.md § "Documentation privacy and path hygiene".
#
# Usage:
#   scripts/attribution_diff.sh --head <ref> [--base <ref>] --from YYYY-MM-DD --to YYYY-MM-DD
#   scripts/attribution_diff.sh --head origin/pull/301/head --from 2026-06-01 --to 2026-06-30
#
# Defaults: --base origin/main. Requires a clean worktree (it checks out refs).
# Exit: 0 = ran (delta may be empty), 2 = setup/usage problem.
set -euo pipefail

BASE="origin/main"
HEAD_REF=""
FROM=""
TO=""

usage() { awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE="${2:?--base needs a ref}"; shift 2 ;;
    --head) HEAD_REF="${2:?--head needs a ref}"; shift 2 ;;
    --from) FROM="${2:?--from needs a date}"; shift 2 ;;
    --to)   TO="${2:?--to needs a date}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "attribution_diff: unknown arg '$1' (try --help)" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "attribution_diff: not inside a git repository" >&2; exit 2; }
cd "$REPO_ROOT"

[[ -n "$HEAD_REF" && -n "$FROM" && -n "$TO" ]] || {
  echo "attribution_diff: --head, --from and --to are required (try --help)." >&2; exit 2; }
if [[ -n "$(git status --porcelain)" ]]; then
  echo "attribution_diff: working tree is dirty — commit or stash first (this checks out refs)." >&2
  exit 2
fi

RUN=(.venv/bin/python timelog_extract.py)
[[ -x .venv/bin/python ]] || RUN=(python3 timelog_extract.py)

# Remember where we were, restore on any exit.
ORIG_REF="$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)"
restore() { git checkout --quiet "$ORIG_REF" 2>/dev/null || true; }
trap restore EXIT

_projects_json() {  # $1 = ref → prints {name: hours} JSON for the window
  git checkout --quiet "$1" 2>/dev/null || { echo "attribution_diff: cannot checkout '$1'." >&2; exit 2; }
  "${RUN[@]}" report --from "$FROM" --to "$TO" --screen-time off --shadow-log off --format json 2>/dev/null \
    | python3 -c "import json,sys; raw=sys.stdin.read(); i=raw.find('{'); print(json.dumps(json.loads(raw[i:]).get('projects',{}), ensure_ascii=False, sort_keys=True) if i>=0 else '{}')"
}

echo "attribution_diff: $BASE  →  $HEAD_REF   window $FROM..$TO" >&2
A="$(_projects_json "$BASE")"
B="$(_projects_json "$HEAD_REF")"

A="$A" B="$B" python3 - <<'PY'
import json, os
a = json.loads(os.environ["A"]); b = json.loads(os.environ["B"])
keys = sorted(set(a) | set(b))
changed = [(k, a.get(k, 0.0), b.get(k, 0.0)) for k in keys if round(a.get(k, 0.0), 3) != round(b.get(k, 0.0), 3)]
print(f"profiles: base={len(a)}  head={len(b)}")
if not changed:
    print("IDENTICAL — the change moves no hours on this window.")
else:
    print("HOURS MOVED (real data — keep local):")
    net = 0.0
    for k, x, y in changed:
        d = y - x; net += d
        print(f"  ~ {k}: {x:.2f}h -> {y:.2f}h  ({d:+.2f})")
    print(f"  net: {net:+.2f}h across {len(changed)} profile(s)")
    print("\nJudge: are the moved hours a correction (were mis-attributed) or a regression (real work dropped)?")
PY
