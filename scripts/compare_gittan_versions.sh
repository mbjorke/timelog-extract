#!/usr/bin/env bash
# Compare release gittan (pipx) vs repo checkout before tagging.
#
# Usage:
#   scripts/compare_gittan_versions.sh
#   scripts/compare_gittan_versions.sh --from 2026-03-01 --to 2026-03-31
#   scripts/compare_gittan_versions.sh --from 2026-06-15 --to 2026-06-15 --from 2026-06-11 --to 2026-06-11
#
# Defaults (no --from/--to): report for today only.
#
# Environment:
#   GITTAN_COMPARE_OLD          Baseline CLI (default: gittan on PATH)
#   GITTAN_COMPARE_NEW          Candidate (default: .venv/bin/python timelog_extract.py if present)
#   GITTAN_COMPARE_SCREEN_TIME  off|on (default: off — fairer cross-version compare)
#   GITTAN_COMPARE_PROJECTS     Space-separated project keys to highlight
#                               (default: timelog-extract financing-portal)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OLD_BIN="${GITTAN_COMPARE_OLD:-gittan}"
if [[ -n "${GITTAN_COMPARE_NEW:-}" ]]; then
  read -r -a NEW_CMD <<<"$GITTAN_COMPARE_NEW"
else
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    NEW_CMD=( "$ROOT/.venv/bin/python" "${TIMELOG_ENTRY:-timelog_extract.py}" )
  else
    NEW_CMD=( "${PYTHON:-python3}" "${TIMELOG_ENTRY:-timelog_extract.py}" )
  fi
fi
SCREEN_TIME="${GITTAN_COMPARE_SCREEN_TIME:-off}"
HIGHLIGHT="${GITTAN_COMPARE_PROJECTS:-timelog-extract financing-portal}"

PERIODS=()
ANY_OBSERVED_DELTA=0

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --from)
      [[ $# -ge 4 && "$3" == --to ]] || { echo "error: use --from DATE --to DATE" >&2; exit 2; }
      PERIODS+=( "$2:$4" )
      shift 4
      ;;
    --to) echo "error: --to must follow --from DATE" >&2; exit 2 ;;
    *) echo "error: unknown argument: $1" >&2; usage 2 ;;
  esac
done

if [[ ${#PERIODS[@]} -eq 0 ]]; then
  today="$(date '+%Y-%m-%d')"
  PERIODS=( "${today}:${today}" )
fi

if ! command -v "$OLD_BIN" >/dev/null 2>&1; then
  echo "error: baseline command not found: $OLD_BIN" >&2
  echo "Set GITTAN_COMPARE_OLD or install pipx release (pipx install timelog-extract)." >&2
  exit 1
fi

version_line() {
  "$@" -V 2>/dev/null | head -1 || echo "(version unknown)"
}

run_report() {
  local from="$1" to="$2"
  shift 2
  "$@" report --quiet --screen-time "$SCREEN_TIME" --from "$from" --to "$to" 2>/dev/null \
    | awk '
        /^Review summary/ { show=1; next }
        show && /^Evidence legend/ { exit }
        show { print }
      '
}

parse_metrics() {
  awk -v highlight="$HIGHLIGHT" '
    function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
    function hours_of(field) {
      gsub(/h/, "", field)
      return field + 0
    }
    function name_and_hours(line,    i, n, parts, pos) {
      n = split(line, parts, /[[:space:]]+/)
      for (i = n; i >= 1; i--) {
        if (parts[i] ~ /^[0-9]+(\.[0-9]+)?h$/) {
          pos = index(line, parts[i])
          return trim(substr(line, 1, pos - 1)) SUBSEP hours_of(parts[i])
        }
      }
      return ""
    }
    BEGIN {
      n = split(highlight, want, " ")
      for (i = 1; i <= n; i++) keys[want[i]] = 1
    }
    /^Observed timeline hours/ {
      print "__observed__\t" hours_of($4)
      next
    }
    /^[[:space:]]*·[[:space:]]/ {
      sub(/^[[:space:]]*·[[:space:]]*/, "")
      pair = name_and_hours($0)
      split(pair, bits, SUBSEP)
      if (bits[1] in keys) print bits[1] "\t" bits[2]
      next
    }
    /^[^[:space:]].*[[:space:]]+[0-9][0-9.]*h/ && $0 !~ /^Project-hour/ && $0 !~ /^Review/ && $0 !~ /^Est\./ && $0 !~ /^Screen/ && $0 !~ /^Delta/ && $0 !~ /^!/ {
      pair = name_and_hours($0)
      if (pair == "") next
      split(pair, bits, SUBSEP)
      print bits[1] "\t" bits[2]
    }
  '
}

compare_metrics() {
  local old_file="$1" new_file="$2"
  awk -F'\t' '
    FNR==NR { old[$1]=$2; next }
    { new[$1]=$2 }
    END {
      for (k in old) seen[k]=1
      for (k in new) seen[k]=1
      for (k in seen) {
        o = (k in old) ? old[k] : -1
        n = (k in new) ? new[k] : -1
        label = k
        if (k == "__observed__") label = "Observed timeline"
        os = (o < 0) ? "—" : sprintf("%.1f", o)
        ns = (n < 0) ? "—" : sprintf("%.1f", n)
        if (o < 0 || n < 0) ds = "—"
        else ds = sprintf("%+.1f", n - o)
        printf "%s\t%s\t%s\t%s\n", label, os, ns, ds
      }
    }
  ' "$old_file" "$new_file" | sort -t$'\t' -k1
}

echo "==> Gittan version compare (repo: $ROOT)"
echo "    OLD: $OLD_BIN  ($(version_line "$OLD_BIN"))"
echo "    NEW: ${NEW_CMD[*]}  ($(version_line "${NEW_CMD[@]}"))"
echo "    screen-time: $SCREEN_TIME"
echo "    highlight projects: $HIGHLIGHT"
echo

for period in "${PERIODS[@]}"; do
  FROM="${period%%:*}"
  TO="${period##*:}"
  label="$FROM"
  [[ "$FROM" != "$TO" ]] && label="${FROM} → ${TO}"

  echo "========== $label =========="
  old_block="$(run_report "$FROM" "$TO" "$OLD_BIN")"
  new_block="$(run_report "$FROM" "$TO" "${NEW_CMD[@]}")"

  old_file="$(mktemp -t gittan-cmp-old.XXXXXX)"
  new_file="$(mktemp -t gittan-cmp-new.XXXXXX)"

  printf '%s\n' "$old_block" | parse_metrics | sort -u >"$old_file"
  printf '%s\n' "$new_block" | parse_metrics | sort -u >"$new_file"

  while IFS=$'\t' read -r key old_h new_h delta; do
    printf "  %-28s  OLD %6s  NEW %6s  Δ %6s\n" "$key" "$old_h" "$new_h" "$delta"
    if [[ "$key" == "Observed timeline" && "$delta" != "—" && "$delta" != "+0.0" && "$delta" != "-0.0" ]]; then
      ANY_OBSERVED_DELTA=1
    fi
  done < <(compare_metrics "$old_file" "$new_file")

  echo
  echo "--- OLD summary ---"
  printf '%s\n' "$old_block" | head -20
  echo "--- NEW summary ---"
  printf '%s\n' "$new_block" | head -20
  echo

  rm -f "$old_file" "$new_file"
done

if [[ "$ANY_OBSERVED_DELTA" -eq 1 ]]; then
  echo "NOTE: Observed timeline differed for at least one period (collectors/session merge)."
  echo "      Project-hour deltas without observed change are usually attribution fixes."
fi

echo "compare_gittan_versions: OK"
