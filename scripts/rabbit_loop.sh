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
#   scripts/rabbit_loop.sh --skip-workflow       # skip GitButler/multi-agent preflight
#   scripts/rabbit_loop.sh --ack-workflow      # record workflow acknowledgement
#   scripts/rabbit_loop.sh --skip-board-sync   # skip project-board PR sync on CONVERGED
#
# --manual-test-plan scaffolds a manual-test checklist from the committed diff:
#   each changed AREA (collectors/outputs/core/cli/scripts/pkg/tests) maps to a
#   concrete verification command for the maintainer to run at a NEEDS_HUMAN pause.
#   To hand that pause to the project board (Status → "Needs manual testing") and
#   post the checklist on the issue, use scripts/rabbit_handoff.sh --issue N.
#
# --classify-merge prints the ship gate for the committed diff vs base:
#   MERGE_CLASS: SAFE        → no human-judgment surface touched; auto-merge when
#                              CONVERGED (per docs/skills/rabbit-loop.md)
#   MERGE_CLASS: NEEDS_HUMAN → touches a judgment surface (report/invoice engine,
#                              collectors, outputs, deps, CI, governance) → pause
#
# Exit codes: 0 = CONVERGED / SAFE, 1 = ITERATE or NEEDS_HUMAN,
#             2 = preflight/setup problem (e.g. not authenticated, or the working
#                 tree moved under the loop — WORKSPACE_MOVED, see below).
#
# GitButler / multi-agent note: this loop makes NO git writes and anchors to the
# branch + HEAD it started on, then classifies any movement at verdict time:
#   - same branch, HEAD advanced (a CodeRabbit autofix or cloud-agent commit) →
#     RABBIT_LOOP: HEAD_ADVANCED (exit 1): re-run to review the new commits.
#   - branch switched / history diverged → RABBIT_LOOP: WORKSPACE_MOVED (exit 2):
#     verdict voided rather than shipping the wrong branch.
#   - gitbutler/* branch → lane churn is expected; the raw-HEAD guard is skipped
#     (lane-scoped truth lives in `but`), so parallel lanes do not void the run.
# For fully isolated parallel work, run in a worktree (scripts/git_worktree.sh add …).

set -euo pipefail

# Default to the remote-tracking ref, not local `main`: a stale local main
# inflates the diff and makes CodeRabbit review unrelated merged work.
BASE="origin/main"
LIGHT=""
RUN_TESTS=1
CLASSIFY=0
MANUAL_PLAN=0
SKIP_WORKFLOW=0
ACK_WORKFLOW=0
SKIP_BOARD_SYNC=0
CLASSIFY_MOVE=0
CLASSIFY_MOVE_BR=""
CLASSIFY_MOVE_SHA=""

usage() {
  awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"
  exit 0
}

# The ship gate is by JUDGMENT, not file type. A change needs a human only when it
# touches a surface where CI + CodeRabbit + autotests cannot judge correctness:
# the report/invoice number engine, captured evidence, visual output, packaging,
# CI, or governance. Everything else auto-merges when CONVERGED — a well-tested fix
# should not need a human to run a command a script already ran.
_judgment_required() {
  case "$1" in
    outputs/*) return 0 ;;                                 # rendering / PDF — visual judgment
    collectors/*) return 0 ;;                              # changes captured evidence → real-data hours
    core/domain.py|core/analytics.py|core/project_hours.py) return 0 ;;   # session / hour math
    core/pipeline.py|core/truth_payload.py) return 0 ;;    # attribution spine
    core/report_*.py) return 0 ;;                          # report engine (all report_* modules)
    pyproject.toml) return 0 ;;                            # deps / packaging
    .github/*) return 0 ;;                                 # CI
    AGENTS.md|CLAUDE.md) return 0 ;;                       # governance
    *) return 1 ;;
  esac
}

# Classify how the working tree moved since LOOP start. Echoes exactly one of:
#   STABLE    same branch, same HEAD — verdict is trustworthy
#   ADVANCED  same branch, HEAD is a descendant of start (auto-commit landed) — re-review
#   MOVED     branch switched, or HEAD diverged (rebase/reset) — verdict void
#   WORKSPACE on gitbutler/* — the integration commit churns as any lane commits, so a
#             raw-HEAD guard is meaningless; lane-scoped truth lives in `but`. We do not
#             void on lane churn (that is the whole point of a GitButler workspace).
_classify_movement() {
  local sbr="$1" ssha="$2" cbr csha
  cbr="$(git branch --show-current 2>/dev/null || echo '')"
  csha="$(git rev-parse HEAD 2>/dev/null || echo '')"
  if [[ "$cbr" == gitbutler/* || "$sbr" == gitbutler/* ]]; then echo "WORKSPACE"; return 0; fi
  if [[ "$cbr" != "$sbr" ]]; then echo "MOVED"; return 0; fi
  if [[ "$csha" == "$ssha" ]]; then echo "STABLE"; return 0; fi
  if [[ -n "$ssha" ]] && git merge-base --is-ancestor "$ssha" "$csha" 2>/dev/null; then
    echo "ADVANCED"
  else
    echo "MOVED"
  fi
}

classify_merge() {
  local base="$1" changed needs=() f
  changed="$(git diff --name-only "${base}...HEAD")"
  if [[ -z "$changed" ]]; then
    echo "MERGE_CLASS: NEEDS_HUMAN (no committed changes vs $base)"; return 1
  fi
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    _judgment_required "$f" && needs+=("$f")
  done <<< "$changed"
  if [[ ${#needs[@]} -eq 0 ]]; then
    echo "MERGE_CLASS: SAFE (no human-judgment surface touched — auto-merge when CONVERGED)"; return 0
  fi
  echo "MERGE_CLASS: NEEDS_HUMAN (${#needs[@]} human-judgment path(s)):"
  printf '  %s\n' "${needs[@]}"
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
    --skip-workflow) SKIP_WORKFLOW=1; shift ;;
    --ack-workflow) ACK_WORKFLOW=1; shift ;;
    --skip-board-sync) SKIP_BOARD_SYNC=1; shift ;;
    # Internal: print the movement class for <start-branch> <start-sha> and exit.
    # Used by tests; not part of the public interface.
    --internal-classify-movement)
      [[ $# -ge 3 ]] || { echo "rabbit_loop: --internal-classify-movement needs <branch> <sha>" >&2; exit 2; }
      CLASSIFY_MOVE_BR="$2"; CLASSIFY_MOVE_SHA="$3"; CLASSIFY_MOVE=1; shift 3 ;;
    -h|--help) usage ;;
    *) echo "rabbit_loop: unknown arg '$1' (try --help)" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "rabbit_loop: not inside a git repository" >&2; exit 2
}
cd "$REPO_ROOT"

# Internal movement classifier (pure git; used by tests). No CodeRabbit call needed.
if [[ $CLASSIFY_MOVE -eq 1 ]]; then
  _classify_movement "$CLASSIFY_MOVE_BR" "$CLASSIFY_MOVE_SHA"; exit 0
fi

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
WORKFLOW_CTX="$REPO_ROOT/scripts/rabbit_workflow_context.sh"

# Anchor the whole run to the branch + HEAD we start on. The loop performs NO git
# writes, so these should stay put for the entire review+test window. But a review
# run takes minutes, and other actors legitimately or accidentally touch the tree:
#   - a CodeRabbit autofix or cloud agent commits ON THE SAME BRANCH (HEAD advances)
#   - a parallel agent `git checkout`s a DIFFERENT branch in a shared clone
#   - someone rebases/resets under our feet (HEAD diverges)
# These are NOT the same event and must not be handled the same way. Auto-commits are
# normal and should trigger a re-review, not a scary "collision" void.
LOOP_START_BR="$(git branch --show-current 2>/dev/null || echo '')"
LOOP_START_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"

# --- workflow preflight (GitButler / multi-agent) ----------------------------
if [[ $SKIP_WORKFLOW -eq 0 ]]; then
  if [[ ! -f "$WORKFLOW_CTX" ]]; then
    echo "rabbit_loop: workflow preflight script missing: $WORKFLOW_CTX" >&2
    exit 2
  fi
  echo "== kanin-loop: workflow preflight (git / GitButler / local lanes) =="
  if [[ $ACK_WORKFLOW -eq 1 ]]; then
    bash "$WORKFLOW_CTX" --ack || exit 2
  fi
  ACK_FILE="$STATE_DIR/workflow.ack"
  HEAD_NOW="$(git rev-parse HEAD 2>/dev/null || true)"
  BR_NOW="$(git branch --show-current 2>/dev/null || true)"
  ACK_OK=0
  if [[ -f "$ACK_FILE" ]]; then
    read -r ack_br ack_sha _ts <"$ACK_FILE" || true
    [[ "$ack_br" == "$BR_NOW" && "$ack_sha" == "$HEAD_NOW" ]] && ACK_OK=1
  fi
  if [[ $ACK_OK -eq 0 ]]; then
    set +e
    bash "$WORKFLOW_CTX"
    WF_EXIT=$?
    set -e
    echo ""
    echo "  Review .rabbit-loop/preflight.html (questions + local task/* lanes + open PRs)."
    if [[ -f "$STATE_DIR/preflight.json" ]]; then
      SUGGESTED="$(python3 -c "
import json,sys
from pathlib import Path
sys.path.insert(0, str(Path(r'''$REPO_ROOT''')/'scripts'))
from rabbit_workflow_context_chat import suggested_chat_title
d=json.load(open(r'''$STATE_DIR/preflight.json'''))
print(suggested_chat_title(d) or '')
" 2>/dev/null || true)"
      if [[ -n "$SUGGESTED" ]]; then
        echo "  Chat title (step 0a): $SUGGESTED"
      else
        echo "  Chat title (step 0a): #<issue> · short topic (set in your editor if available)"
      fi
    fi
    echo "  Then: scripts/rabbit_workflow_context.sh --ack   or   scripts/rabbit_loop.sh --ack-workflow"
    if [[ $WF_EXIT -eq 2 ]]; then
      echo "rabbit_loop: workflow BLOCKERS — resolve before CodeRabbit (or --skip-workflow)." >&2
      exit 2
    fi
    echo "rabbit_loop: workflow acknowledgement required before CodeRabbit." >&2
    exit 2
  fi
  echo ""
fi

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
# The review + tests only mean something if they ran against the state we started on.
# Classify what (if anything) moved and act accordingly — never write converged.ack or
# sync the board for a branch we did not actually review.
MOVE_CLASS="$(_classify_movement "$LOOP_START_BR" "$LOOP_START_SHA")"
case "$MOVE_CLASS" in
  STABLE) : ;;
  WORKSPACE)
    echo "  note: GitButler workspace detected — lane churn is expected; the raw-HEAD" >&2
    echo "        guard is skipped. Lane-scoped verification lives in \`but\`; a re-run" >&2
    echo "        picks up any lane commit. (Do not merge a lane you did not review.)" >&2
    ;;
  ADVANCED)
    NOW_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"
    echo "RABBIT_LOOP: HEAD_ADVANCED — new commits landed on $LOOP_START_BR since the review"
    echo "  started ${LOOP_START_SHA:0:12} → now ${NOW_SHA:0:12} (e.g. a CodeRabbit autofix"
    echo "  or cloud-agent commit). The review did not cover them — re-run to review the new"
    echo "  HEAD before shipping. (Verdict withheld, not failed.)"
    exit 1
    ;;
  MOVED|*)
    NOW_BR="$(git branch --show-current 2>/dev/null || echo '')"
    NOW_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"
    echo "" >&2
    echo "RABBIT_LOOP: WORKSPACE_MOVED — the working tree changed under the loop." >&2
    echo "  started on: ${LOOP_START_BR:-<detached>} @ ${LOOP_START_SHA:0:12}" >&2
    echo "  now on:     ${NOW_BR:-<detached>} @ ${NOW_SHA:0:12}" >&2
    echo "  A parallel checkout or history rewrite moved HEAD to unrelated work; the" >&2
    echo "  review/test result is not trustworthy for either branch. Verdict voided." >&2
    echo "  Re-run in an isolated worktree: scripts/git_worktree.sh add ${LOOP_START_BR:-<branch>}" >&2
    exit 2
    ;;
esac
# A review that did not complete cleanly must never read as CONVERGED.
if [[ $CR_EXIT -ne 0 || "$REVIEW_COMPLETED" != "1" ]]; then
  echo "RABBIT_LOOP: REVIEW_INCOMPLETE (cr_exit=$CR_EXIT completed=$REVIEW_COMPLETED) — see $FINDINGS_FILE"
  exit 1
fi
# CONVERGED is the ship signal — it requires green tests, never skipped ones.
if [[ "$FINDINGS_COUNT" == "0" && "$TESTS_STATUS" == "PASS" ]]; then
  printf '%s %s %s\n' "$(git branch --show-current 2>/dev/null || echo '')" \
    "$(git rev-parse HEAD 2>/dev/null || echo '')" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$STATE_DIR/converged.ack"
  echo "RABBIT_LOOP: CONVERGED (findings=0 tests=PASS)"
  if [[ $SKIP_BOARD_SYNC -eq 0 && -f "$REPO_ROOT/scripts/rabbit_board_sync.sh" ]]; then
    # Wrap in a wall-clock timeout so a hung gh/network call can never stall the
    # loop's ship signal. timeout(1) is GNU coreutils (gtimeout on macOS/brew);
    # fall back to no wrapper when neither is present (Python side caps each gh
    # call at 30s regardless).
    BOARD_TIMEOUT=()
    if command -v timeout >/dev/null 2>&1; then BOARD_TIMEOUT=(timeout 60)
    elif command -v gtimeout >/dev/null 2>&1; then BOARD_TIMEOUT=(gtimeout 60); fi
    set +e
    BOARD_SYNC_OUT="$(${BOARD_TIMEOUT[@]+"${BOARD_TIMEOUT[@]}"} bash "$REPO_ROOT/scripts/rabbit_board_sync.sh" --status "In review" 2>&1)"
    BOARD_SYNC_RC=$?
    set -e
    [[ -n "$BOARD_SYNC_OUT" ]] && printf '%s\n' "$BOARD_SYNC_OUT" | sed 's/^/  board: /'
    # exit 3 = no open PR yet (normal before gh pr create); 124 = timeout(1) expiry
    if [[ $BOARD_SYNC_RC -eq 124 ]]; then
      echo "  board: warning: sync timed out; continuing" >&2
    elif [[ $BOARD_SYNC_RC -ne 0 && $BOARD_SYNC_RC -ne 3 ]]; then
      echo "  board: warning: sync failed with exit $BOARD_SYNC_RC; continuing" >&2
    fi
  fi
  exit 0
fi
if [[ "$FINDINGS_COUNT" == "0" && "$TESTS_STATUS" == "SKIPPED" ]]; then
  echo "RABBIT_LOOP: REVIEW_CLEAN (findings=0, tests skipped — rerun without --no-tests to converge)"
  exit 1
fi
echo "RABBIT_LOOP: ITERATE (findings=$FINDINGS_COUNT tests=$TESTS_STATUS)"
echo "  Read $FINDINGS_FILE, fix within docs/decisions/agent-review-contract.md, then rerun."
exit 1
