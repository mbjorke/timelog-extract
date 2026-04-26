#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FROM_DATE=""
TO_DATE=""
OUT_DIR=""
PROJECTS_CONFIG=""
ALLOW_OPEN_WINDOW=0

usage() {
  cat <<'EOF'
Usage: bash scripts/timelog_truth_check.sh --from YYYY-MM-DD --to YYYY-MM-DD [options]

Options:
  --from DATE              Start date (required)
  --to DATE                End date (required)
  --out-dir DIR            Output directory (default: out/timelog_truth_check/<timestamp>)
  --projects-config PATH   Optional projects config path
  --allow-open-window      Allow --to equal today's date (normally blocked)

Artifacts written:
  - benchmark_manifest.json
  - benchmark_metrics.json
  - determinism_replay_report.json
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      FROM_DATE="${2:-}"
      shift 2
      ;;
    --to)
      TO_DATE="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --projects-config)
      PROJECTS_CONFIG="${2:-}"
      shift 2
      ;;
    --allow-open-window)
      ALLOW_OPEN_WINDOW=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$FROM_DATE" || -z "$TO_DATE" ]]; then
  echo "Error: --from and --to are required." >&2
  usage
  exit 1
fi

TODAY="$(date '+%Y-%m-%d')"
if [[ "$TO_DATE" == "$TODAY" && "$ALLOW_OPEN_WINDOW" -ne 1 ]]; then
  echo "Error: --to is today ($TODAY). Use a closed window or pass --allow-open-window." >&2
  exit 1
fi

if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="out/timelog_truth_check/$(date '+%Y%m%d-%H%M%S')"
fi

mkdir -p "$OUT_DIR"

RUN1_JSON="$OUT_DIR/run1.json"
RUN2_JSON="$OUT_DIR/run2.json"
MANIFEST_JSON="$OUT_DIR/benchmark_manifest.json"
METRICS_JSON="$OUT_DIR/benchmark_metrics.json"
REPLAY_JSON="$OUT_DIR/determinism_replay_report.json"
README_MD="$OUT_DIR/README.md"

REPORT_CMD=(python3 -m timelog_extract report --from "$FROM_DATE" --to "$TO_DATE" --format json)
if [[ -n "$PROJECTS_CONFIG" ]]; then
  REPORT_CMD+=(--projects-config "$PROJECTS_CONFIG")
fi

echo "Running timelog truth check..."
echo "- from: $FROM_DATE"
echo "- to:   $TO_DATE"
echo "- out:  $OUT_DIR"

"${REPORT_CMD[@]}" --json-file "$RUN1_JSON" >/dev/null
"${REPORT_CMD[@]}" --json-file "$RUN2_JSON" >/dev/null

python3 - "$FROM_DATE" "$TO_DATE" "$RUN1_JSON" "$RUN2_JSON" "$MANIFEST_JSON" "$METRICS_JSON" "$REPLAY_JSON" "$README_MD" "$TODAY" "$ALLOW_OPEN_WINDOW" <<'PY'
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

(
    date_from,
    date_to,
    run1_path,
    run2_path,
    manifest_path,
    metrics_path,
    replay_path,
    readme_path,
    today,
    allow_open_window,
) = sys.argv[1:]

run1 = json.loads(Path(run1_path).read_text(encoding="utf-8"))
run2 = json.loads(Path(run2_path).read_text(encoding="utf-8"))

VOLATILE = {"generated_at", "runtime_ms", "elapsed_ms"}

def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value

norm1 = scrub(run1)
norm2 = scrub(run2)

norm1_text = json.dumps(norm1, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
norm2_text = json.dumps(norm2, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
hash1 = hashlib.sha256(norm1_text.encode("utf-8")).hexdigest()
hash2 = hashlib.sha256(norm2_text.encode("utf-8")).hexdigest()
normalized_equal = hash1 == hash2

def collect_diff_keys(a, b, prefix=""):
    diffs = []
    if type(a) is not type(b):
        return [prefix or "<root>"]
    if isinstance(a, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            p = f"{prefix}.{k}" if prefix else k
            if k not in a or k not in b:
                diffs.append(p)
            else:
                diffs.extend(collect_diff_keys(a[k], b[k], p))
        return diffs
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{prefix}.length" if prefix else "<root>.length"]
        for i, (x, y) in enumerate(zip(a, b)):
            p = f"{prefix}[{i}]" if prefix else f"[{i}]"
            diffs.extend(collect_diff_keys(x, y, p))
        return diffs
    if a != b:
        return [prefix or "<root>"]
    return []

drift_keys = collect_diff_keys(norm1, norm2)[:200]

date_start = dt.date.fromisoformat(date_from)
date_end = dt.date.fromisoformat(date_to)
months = []
cursor = dt.date(date_start.year, date_start.month, 1)
while cursor <= date_end:
    months.append(cursor.strftime("%Y-%m"))
    if cursor.month == 12:
        cursor = dt.date(cursor.year + 1, 1, 1)
    else:
        cursor = dt.date(cursor.year, cursor.month + 1, 1)

projects_obj = run1.get("projects", {})
if isinstance(projects_obj, dict):
    projects_in_scope = sorted(projects_obj.keys())
else:
    projects_in_scope = []

project_inclusion_reasons = {name: "included_activity_detected" for name in projects_in_scope}

policy_package = {
    "policy_version": "draft",
    "rule_bundle_sha": "unknown",
    "scoring_profile": "unknown",
    "threshold_profile": "unknown",
    "volatile_field_allowlist_version": "v1-draft",
    "normalization_profile_version": "v1-draft",
}

manifest = {
    "target_year": date_start.year,
    "months_in_scope": months,
    "projects_in_scope": projects_in_scope,
    "project_inclusion_reasons": project_inclusion_reasons,
    "project_exclusions": [],
    "policy_package": policy_package,
}

is_open_window = date_to == today
if normalized_equal:
    gate_decision = "GO"
elif is_open_window and allow_open_window == "1":
    gate_decision = "conditional GO"
else:
    gate_decision = "NO-GO"

metrics = {
    "precision_recall_f1_by_project": None,
    "customer_hour_drift": None,
    "review_load": None,
    "explainability_coverage": None,
    "annual_coverage": None,
    "gate_decision": gate_decision,
    "gate_failures": ([] if normalized_equal else ["determinism_replay_mismatch"]),
}

replay = {
    "replay_runs": [str(Path(run1_path).name), str(Path(run2_path).name)],
    "payload_hashes": {"run1": hash1, "run2": hash2},
    "normalized_equal": normalized_equal,
    "volatile_field_allowlist_version": "v1-draft",
    "drift_keys": drift_keys,
    "determinism_status": "ok" if normalized_equal else "degraded",
}

Path(manifest_path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
Path(metrics_path).write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
Path(replay_path).write_text(json.dumps(replay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
Path(readme_path).write_text(
    "\n".join(
        [
            "# Timelog Truth Check Artifacts",
            "",
            f"- window: {date_from} -> {date_to}",
            f"- normalized_equal: {normalized_equal}",
            f"- gate_decision: {gate_decision}",
            "",
            "## Files",
            "",
            "- benchmark_manifest.json: scope + policy package metadata",
            "- benchmark_metrics.json: gate decision and quality metrics",
            "- determinism_replay_report.json: replay hashes and drift details",
            "",
            "## How to read results",
            "",
            "- `normalized_equal=true` means deterministic replay passed for this window.",
            "- `gate_decision=GO` means no determinism mismatch was detected.",
            "- If `drift_keys` is non-empty, inspect determinism_replay_report.json first.",
            "",
        ]
    )
    + "\n",
    encoding="utf-8",
)

print(f"normalized_equal={normalized_equal}")
print(f"gate_decision={gate_decision}")
print(f"drift_keys={len(drift_keys)}")
PY

echo ""
echo "Artifacts:"
echo "- $MANIFEST_JSON"
echo "- $METRICS_JSON"
echo "- $REPLAY_JSON"
echo "- $README_MD"
