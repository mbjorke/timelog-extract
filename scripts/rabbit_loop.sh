#!/usr/bin/env bash
# rabbit_loop.sh — one iteration of the CodeRabbit "kanin-loop".
#
# Loop-engineering harness: runs the two independent critics on the current
# local diff and reports whether the work has CONVERGED.
#   1. CodeRabbit  — `coderabbit review --agent` (structured findings)
#   2. Autotests   — `scripts/run_autotests.sh` (500-line gate + unit tests)
#
# It does NOT edit code, commit, push, or merge. The agent/human reads the
# findings, applies fixes within docs/decisions/agent-review-contract.md, then
# runs this again. Canonical workflow: docs/skills/rabbit-loop.md.
#
# Usage:
#   scripts/rabbit_loop.sh [--base <branch>] [--light] [--no-tests] [--help]
#   scripts/rabbit_loop.sh --classify-merge [--base <branch>]
#   scripts/rabbit_loop.sh --manual-test-plan [--base <branch>]
#
# --manual-test-plan scaffolds a manual-test checklist from the committed diff:
#   each changed AREA (collectors/outputs/core/cli/scripts/pkg/tests) maps to a
#   concrete verification command for the maintainer to run at a NEEDS_HUMAN pause.
#
# --classify-merge prints the ship gate for the committed diff vs base:
#   MERGE_CLASS: SAFE        → only docs/, .claude/skills/, .cursor/rules/ changed
#                              (auto-merge permitted by docs/skills/rabbit-loop.md)
#   MERGE_CLASS: NEEDS_HUMAN → any shipping/behavior/config path changed → pause
#
# Exit codes: 0 = CONVERGED / SAFE, 1 = ITERATE or NEEDS_HUMAN,
#             2 = preflight/setup problem (e.g. not authenticated).

set -euo pipefail

# Default to the remote-tracking ref, not local `main`: a stale local main
# inflates the diff and makes CodeRabbit review unrelated merged work.
BASE="origin/main"
LIGHT=""
RUN_TESTS=1
CLASSIFY=0
MANUAL_PLAN=0

# Auto-merge is permitted ONLY when every committed path lives under one of these
# non-shipping prefixes. Anything touching core/, collectors/, outputs/, scripts/,
# tests/, config, or governance falls through to NEEDS_HUMAN (pause). Conservative
# by design: a misclassified auto-merge is worse than an unnecessary pause.
SAFE_MERGE_PREFIXES=("docs/" ".claude/skills/" ".cursor/rules/")

usage() {
  awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"
  exit 0
}

classify_merge() {
  local base="$1" changed unsafe=() f p ok
  changed="$(git diff --name-only "${base}...HEAD")"
  if [[ -z "$changed" ]]; then
    echo "MERGE_CLASS: NEEDS_HUMAN (no committed changes vs $base)"; return 1
  fi
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    ok=0
    for p in "${SAFE_MERGE_PREFIXES[@]}"; do
      [[ "$f" == "$p"* ]] && { ok=1; break; }
    done
    [[ $ok -eq 0 ]] && unsafe+=("$f")
  done <<< "$changed"
  if [[ ${#unsafe[@]} -eq 0 ]]; then
    echo "MERGE_CLASS: SAFE (docs/skills/rules only)"; return 0
  fi
  echo "MERGE_CLASS: NEEDS_HUMAN (${#unsafe[@]} shipping/behavior path(s)):"
  printf '  %s\n' "${unsafe[@]}"
  return 1
}

# Scaffold a manual-test checklist from the committed diff, mapping each changed
# AREA to a concrete verification command. The agent completes each step's
# "Expected:" with a judgeable outcome before handing it to the maintainer.
manual_test_plan() {
  local base="$1" changed f
  changed="$(git diff --name-only "${base}...HEAD")"
  if [[ -z "$changed" ]]; then
    echo "No committed changes vs $base — nothing to manually test."; return 0
  fi
  local a_col=0 a_out=0 a_core=0 a_cli=0 a_scr=0 a_pkg=0 a_tst=0 a_doc=0
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    case "$f" in
      collectors/*)               a_col=1 ;;
      outputs/*)                   a_out=1 ;;
      core/cli*|timelog_extract.py) a_cli=1 ;;
      core/*)                      a_core=1 ;;
      tests/*)                     a_tst=1 ;;
      scripts/*)                   a_scr=1 ;;
      pyproject.toml)              a_pkg=1 ;;
      docs/*|.cursor/*|.claude/*|*.md) a_doc=1 ;;
      *)                           a_core=1 ;;  # unknown → treat as behavior
    esac
  done <<< "$changed"

  local -a steps=()
  [[ $a_col -eq 1 ]] && steps+=("Source health (collectors/): \`gittan-dev doctor\` → changed source shows the right collector_status row; \`gittan-dev report --today --source-summary\` → it contributes events (or is correctly empty). Expected: <fill>")
  [[ $a_out -eq 1 ]] && steps+=("Rendering (outputs/): \`gittan-dev report --from <window> --to <window> --screen-time off\` → the affected table/section renders (columns, grouping, totals). Expected: <fill>")
  [[ $a_core -eq 1 ]] && steps+=("Behavior (core/): \`bash scripts/run_autotests.sh\` green, then \`gittan-dev report --from <window> --to <window>\` on a known window → hours/grouping match expectation. Expected: <fill>")
  [[ $a_cli -eq 1 ]] && steps+=("CLI: \`gittan-dev <changed-command> --help\` renders; run a representative invocation → correct output + exit code. Expected: <fill>")
  [[ $a_scr -eq 1 ]] && steps+=("Script (scripts/): run it with \`--help\` and a representative invocation → expected behavior + exit code. Expected: <fill>")
  [[ $a_pkg -eq 1 ]] && steps+=("Packaging (pyproject.toml): \`python -m build\` succeeds; smoke-install the wheel; \`gittan -V\`. Expected: <fill>")
  [[ $a_tst -eq 1 ]] && steps+=("Targeted tests: \`python3 -m unittest tests/<changed_test>.py\` → green. Expected: <fill>")
  [[ $a_doc -eq 1 && ${#steps[@]} -eq 0 ]] && steps+=("Docs/config only: skim rendering; no runtime test expected. Expected: <fill or 'n/a'>")

  cat <<'HDR'
# Manual-test checklist

Change: <one line — what this branch does>
Why manual: <what CodeRabbit + autotests cannot verify>

Run each step; record a judgeable result (command + expected outcome — no "looks right").
HDR
  local i=1 s
  for s in "${steps[@]}"; do
    printf '\n%d. %s\n' "$i" "$s"
    i=$((i + 1))
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE="${2:?--base needs a branch}"; shift 2 ;;
    --light) LIGHT="--light"; shift ;;
    --no-tests) RUN_TESTS=0; shift ;;
    --classify-merge) CLASSIFY=1; shift ;;
    --manual-test-plan) MANUAL_PLAN=1; shift ;;
    -h|--help) usage ;;
    *) echo "rabbit_loop: unknown arg '$1' (try --help)" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "rabbit_loop: not inside a git repository" >&2; exit 2
}
cd "$REPO_ROOT"

# Ship-gate classification and the manual-test scaffold are pure git-diff checks;
# no CodeRabbit call needed.
if [[ $CLASSIFY -eq 1 || $MANUAL_PLAN -eq 1 ]]; then
  if ! git rev-parse --verify --quiet "$BASE" >/dev/null; then
    echo "rabbit_loop: base ref '$BASE' not found (try \`git fetch origin\`)." >&2; exit 2
  fi
  [[ $CLASSIFY -eq 1 ]] && { classify_merge "$BASE"; exit $?; }
  manual_test_plan "$BASE"; exit 0
fi

STATE_DIR="$REPO_ROOT/.rabbit-loop"
mkdir -p "$STATE_DIR"
FINDINGS_FILE="$STATE_DIR/findings.txt"
TESTS_LOG="$STATE_DIR/autotests.log"

# --- preflight -------------------------------------------------------------
if ! command -v coderabbit >/dev/null 2>&1; then
  echo "rabbit_loop: CodeRabbit CLI not found. Install it, then \`coderabbit auth login\`." >&2
  exit 2
fi
if ! coderabbit auth status >/dev/null 2>&1; then
  echo "rabbit_loop: CodeRabbit is not authenticated — run \`coderabbit auth login\`." >&2
  exit 2
fi
if ! git rev-parse --verify --quiet "$BASE" >/dev/null; then
  echo "rabbit_loop: base ref '$BASE' not found. Fetch it (\`git fetch origin\`) or pass --base." >&2
  exit 2
fi
# A local base that lags its remote inflates the diff (CodeRabbit reviews merged
# work you did not touch). Warn so the operator can `git fetch`.
if [[ "$BASE" != */* ]] && git rev-parse --verify --quiet "origin/$BASE" >/dev/null; then
  if [[ "$(git rev-parse "$BASE")" != "$(git rev-parse "origin/$BASE")" ]]; then
    echo "rabbit_loop: warning — local '$BASE' differs from 'origin/$BASE'; the review may cover" >&2
    echo "  unrelated merged work. Consider --base origin/$BASE or \`git fetch\`." >&2
  fi
fi

echo "== kanin-loop: CodeRabbit review (base=$BASE${LIGHT:+, light}) =="
set +e
coderabbit review --agent --base "$BASE" --type all $LIGHT >"$FINDINGS_FILE" 2>&1
CR_EXIT=$?
set -e

# Parse the JSONL --agent stream once. The authoritative signal is the
# `complete` event: {"type":"complete","status":"review_completed","findings":N}.
# We fail closed if it is missing or status != review_completed. Python prints
# the human summary to stderr and "<completed> <count>" to stdout.
PARSE="$(python3 - "$FINDINGS_FILE" <<'PY'
import json, sys
completed, count, findings = False, None, []
with open(sys.argv[1]) as f:
    for line in f:
        try:
            o = json.loads(line)
        except ValueError:
            continue
        t = o.get("type")
        if t == "finding":
            findings.append(f"  [{o.get('severity','?')}] {o.get('fileName','?')}")
        elif t == "complete":
            completed = o.get("status") == "review_completed"
            if o.get("findings") is not None:
                count = int(o["findings"])
if count is None:
    count = len(findings)
sys.stderr.write(("\n".join(findings) + "\n") if findings else "CodeRabbit findings: 0\n")
print(f"{1 if completed else 0} {count}")
PY
)" || PARSE="0 0"
REVIEW_COMPLETED="${PARSE%% *}"
FINDINGS_COUNT="${PARSE##* }"

# --- autotests -------------------------------------------------------------
TESTS_STATUS="SKIPPED"
if [[ $RUN_TESTS -eq 1 ]]; then
  echo ""
  echo "== kanin-loop: autotests =="
  set +e
  bash scripts/run_autotests.sh >"$TESTS_LOG" 2>&1
  TESTS_EXIT=$?
  set -e
  tail -3 "$TESTS_LOG"
  if [[ $TESTS_EXIT -eq 0 ]]; then TESTS_STATUS="PASS"; else TESTS_STATUS="FAIL"; fi
fi

# --- verdict (fail closed) -------------------------------------------------
echo ""
# A review that did not complete cleanly must never read as CONVERGED.
if [[ $CR_EXIT -ne 0 || "$REVIEW_COMPLETED" != "1" ]]; then
  echo "RABBIT_LOOP: REVIEW_INCOMPLETE (cr_exit=$CR_EXIT completed=$REVIEW_COMPLETED) — see $FINDINGS_FILE"
  exit 1
fi
# CONVERGED is the ship signal — it requires green tests, never skipped ones.
if [[ "$FINDINGS_COUNT" == "0" && "$TESTS_STATUS" == "PASS" ]]; then
  echo "RABBIT_LOOP: CONVERGED (findings=0 tests=PASS)"
  exit 0
fi
if [[ "$FINDINGS_COUNT" == "0" && "$TESTS_STATUS" == "SKIPPED" ]]; then
  echo "RABBIT_LOOP: REVIEW_CLEAN (findings=0, tests skipped — rerun without --no-tests to converge)"
  exit 1
fi
echo "RABBIT_LOOP: ITERATE (findings=$FINDINGS_COUNT tests=$TESTS_STATUS)"
echo "  Read $FINDINGS_FILE, fix within docs/decisions/agent-review-contract.md, then rerun."
exit 1
