#!/usr/bin/env bash
set -euo pipefail

# Contributor helper for repeatable setup + triage manual UX checks.
# Keeps local machine state safe by writing project config to a temp file.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

triage_cmd() {
  local from="${GITTAN_TRIAGE_FROM:-}"
  local to="${GITTAN_TRIAGE_TO:-}"
  local max_days="${GITTAN_TRIAGE_MAX_DAYS:-1}"
  local max_sites="${GITTAN_TRIAGE_MAX_SITES:-5}"
  if [[ -n "$from" && -n "$to" ]]; then
    python3 timelog_extract.py triage --json --from "$from" --to "$to" --max-days "$max_days" --max-sites "$max_sites"
  else
    python3 timelog_extract.py triage --json --max-days "$max_days" --max-sites "$max_sites"
  fi
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/contributor_setup_scenarios.sh <scenario-name> [source-config]

Optional env for non-interactive triage recordings:
  GITTAN_TRIAGE_FROM=YYYY-MM-DD
  GITTAN_TRIAGE_TO=YYYY-MM-DD
  GITTAN_TRIAGE_MAX_DAYS=1
  GITTAN_TRIAGE_MAX_SITES=5

Scenarios:
  new-customer-from-scratch
      Empty project config + interactive setup + triage JSON.
      Focus: first-time onboarding with explicit mapping approvals.

  mapping-rerun-safety
      Same flow as above, but with prompts focused on rerun safety.
      Focus: edit/previous behavior and "safe to rerun" confidence.

  triage-only-evidence-review
      Skip setup, run interactive triage JSON on a temporary empty config.
      Focus: timeframe picker and evidence candidate readability.

  real-config-sandbox
      Copy your real projects config to a temporary sandbox file.
      Focus: validate setup + triage behavior on realistic data without touching source config.

  anonymized-demo-config
      Build an anonymized temporary config derived from real config.
      Focus: demo-safe structure preserving project count and mapping shape.

Examples:
  bash scripts/contributor_setup_scenarios.sh new-customer-from-scratch
  bash scripts/contributor_setup_scenarios.sh mapping-rerun-safety
  bash scripts/contributor_setup_scenarios.sh triage-only-evidence-review
  bash scripts/contributor_setup_scenarios.sh real-config-sandbox
  bash scripts/contributor_setup_scenarios.sh anonymized-demo-config
  bash scripts/contributor_setup_scenarios.sh real-config-sandbox /path/to/timelog_projects.json
EOF
}

print_checklist() {
  local scenario="$1"
  echo
  echo "Scenario: $scenario"
  echo "What to validate:"
  if [[ "$scenario" == "new-customer-from-scratch" ]]; then
    echo "  1) Can you add customers from an empty config without hidden writes?"
    echo "  2) Is project mapping explicit per project before save?"
    echo "  3) After setup, does triage JSON show evidence candidates clearly?"
  else
    echo "  1) Does 'Edit customer list...' preserve existing entered customers?"
    echo "  2) Can you use 'Previous project' to safely correct an earlier choice?"
    echo "  3) Are skipped projects left untouched as expected?"
  fi
  if [[ "$scenario" == "triage-only-evidence-review" ]]; then
    echo "  1) Does triage show timeframe picker when date flags are omitted?"
    echo "  2) Is progress visible while JSON evidence is being produced?"
    echo "  3) Are evidence candidates understandable without extra flags?"
  fi
  if [[ "$scenario" == "real-config-sandbox" ]]; then
    echo "  1) Does setup preserve your intended mappings on realistic data?"
    echo "  2) Do triage candidates look sensible for your active projects?"
    echo "  3) Is your original config file unchanged after the run?"
  fi
  if [[ "$scenario" == "anonymized-demo-config" ]]; then
    echo "  1) Are project/customer names anonymized consistently?"
    echo "  2) Does triage still produce structurally useful evidence output?"
    echo "  3) Is the anonymized file safe for demo-sharing?"
  fi
  echo
}

resolve_real_config_path() {
  local explicit="${1:-}"
  if [[ -n "$explicit" ]]; then
    echo "$explicit"
    return 0
  fi
  (
    cd "$ROOT_DIR"
    python3 - <<'PY'
from core.config import resolve_projects_config_path
print(resolve_projects_config_path())
PY
  )
}

run_setup_and_triage_json() {
  local tmpcfg
  tmpcfg="$(mktemp /tmp/gittan-contrib-setup.XXXXXX)"
  printf '{"version":1,"projects":[]}\n' > "$tmpcfg"

  echo "Using temporary project config: $tmpcfg"
  echo "This file is disposable and only for this scenario run."
  echo

  (
    cd "$ROOT_DIR"
    GITTAN_PROJECTS_CONFIG="$tmpcfg" python3 timelog_extract.py setup --interactive --skip-smoke
    GITTAN_PROJECTS_CONFIG="$tmpcfg" triage_cmd
  )

  echo
  echo "Scenario completed."
  echo "Temp config kept for inspection: $tmpcfg"
}

run_triage_only_json() {
  local tmpcfg
  tmpcfg="$(mktemp /tmp/gittan-contrib-triage.XXXXXX)"
  printf '{"version":1,"projects":[]}\n' > "$tmpcfg"

  echo "Using temporary project config: $tmpcfg"
  echo "Running triage evidence review only (no setup)."
  echo

  (
    cd "$ROOT_DIR"
    GITTAN_PROJECTS_CONFIG="$tmpcfg" triage_cmd
  )

  echo
  echo "Scenario completed."
  echo "Temp config kept for inspection: $tmpcfg"
}

run_real_config_sandbox() {
  local source_cfg="$1"
  local tmpcfg
  tmpcfg="$(mktemp /tmp/gittan-contrib-real.XXXXXX)"
  cp "$source_cfg" "$tmpcfg"

  echo "Source config: $source_cfg"
  echo "Sandbox copy:  $tmpcfg"
  echo "Original file remains untouched."
  echo

  (
    cd "$ROOT_DIR"
    GITTAN_PROJECTS_CONFIG="$tmpcfg" python3 timelog_extract.py setup --interactive --skip-smoke
    GITTAN_PROJECTS_CONFIG="$tmpcfg" triage_cmd
  )

  echo
  echo "Scenario completed."
  echo "Sandbox config kept for inspection: $tmpcfg"
}

run_anonymized_demo_config() {
  local source_cfg="$1"
  local tmpcfg
  tmpcfg="$(mktemp /tmp/gittan-contrib-anon.XXXXXX)"
  cp "$source_cfg" "$tmpcfg"

  (
    cd "$ROOT_DIR"
    python3 - "$tmpcfg" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
projects = payload.get("projects", [])
if not isinstance(projects, list):
    projects = []
    payload["projects"] = projects

customer_map = {}
term_map = {}
url_map = {}
customer_idx = 0
term_idx = 0
url_idx = 0

def map_customer(value: str) -> str:
    global customer_idx
    v = (value or "").strip()
    if not v:
        return v
    if v not in customer_map:
        customer_idx += 1
        customer_map[v] = f"customer-{customer_idx:03d}.example"
    return customer_map[v]

def map_term(value: str) -> str:
    global term_idx
    v = (value or "").strip()
    if not v:
        return v
    if v not in term_map:
        term_idx += 1
        term_map[v] = f"term-{term_idx:03d}"
    return term_map[v]

def map_url(value: str) -> str:
    global url_idx
    v = (value or "").strip()
    if not v:
        return v
    if v not in url_map:
        url_idx += 1
        url_map[v] = f"domain-{url_idx:03d}.example"
    return url_map[v]

for i, project in enumerate(projects, start=1):
    if not isinstance(project, dict):
        continue
    anon_name = f"project-{i:03d}"
    project["name"] = anon_name
    project["project_id"] = anon_name
    project["canonical_project"] = anon_name

    customer = map_customer(str(project.get("customer", "")).strip() or anon_name)
    project["customer"] = customer
    project["default_client"] = map_customer(str(project.get("default_client", "")).strip() or customer)
    project["aliases"] = [anon_name]
    project["match_terms"] = [map_term(str(t)) for t in (project.get("match_terms") or []) if str(t).strip()]
    project["tracked_urls"] = [map_url(str(u)) for u in (project.get("tracked_urls") or []) if str(u).strip()]
    project["email"] = ""
    project["invoice_title"] = ""
    project["invoice_description"] = ""
    if "tags" in project and isinstance(project["tags"], list):
        project["tags"] = [f"tag-{idx+1:02d}" for idx, _ in enumerate(project["tags"])]

path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Anonymized config written: {path}")
print(f"Projects anonymized: {len([p for p in projects if isinstance(p, dict)])}")
PY
  )

  echo "Using anonymized temp config: $tmpcfg"
  echo
  (
    cd "$ROOT_DIR"
    GITTAN_PROJECTS_CONFIG="$tmpcfg" triage_cmd
  )

  echo
  echo "Scenario completed."
  echo "Anonymized demo config kept for inspection: $tmpcfg"
}

main() {
  if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage
    exit 1
  fi
  local source_cfg_arg="${2:-}"

  case "$1" in
    new-customer-from-scratch|mapping-rerun-safety)
      print_checklist "$1"
      run_setup_and_triage_json
      ;;
    triage-only-evidence-review)
      print_checklist "$1"
      run_triage_only_json
      ;;
    real-config-sandbox)
      print_checklist "$1"
      source_cfg_arg="$(resolve_real_config_path "$source_cfg_arg")"
      if [[ ! -f "$source_cfg_arg" ]]; then
        echo "Source config not found: $source_cfg_arg" >&2
        exit 1
      fi
      run_real_config_sandbox "$source_cfg_arg"
      ;;
    anonymized-demo-config)
      print_checklist "$1"
      source_cfg_arg="$(resolve_real_config_path "$source_cfg_arg")"
      if [[ ! -f "$source_cfg_arg" ]]; then
        echo "Source config not found: $source_cfg_arg" >&2
        exit 1
      fi
      run_anonymized_demo_config "$source_cfg_arg"
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      echo "Unknown scenario: $1" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
