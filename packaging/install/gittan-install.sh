#!/usr/bin/env bash
# gittan — one-liner installer (https://gittan.sh)
#
# Canonical source lives in the Gittan app repo:
#   timelog-extract/packaging/install/gittan-install.sh
# `https://gittan.sh/install` mirrors this file via the gittan-home repo.
#
# Usage:
#   curl -fsSL https://gittan.sh/install | bash
#   curl -fsSL https://gittan.sh/install | bash -s -- --dry-run
#   curl -fsSL https://gittan.sh/install | bash -s -- --version 0.2.20
#   curl -fsSL https://gittan.sh/install | bash -s -- --help
#
# What it does:
#   - verifies Python 3.9+ is available
#   - installs gittan via pipx (preferred) or `pip install --user` as a fallback
#   - prints `gittan -V` to confirm
#
# The script does not read stdin, so piping from curl into bash is safe.
set -euo pipefail

PACKAGE="timelog-extract"   # PyPI package name
COMMAND="gittan"            # CLI command this puts on your PATH
PY_MIN_MAJOR=3
PY_MIN_MINOR=9
PYPI_BASE="https://pypi.org/project"

DRY_RUN=0
PIN_VERSION=""

print_help() {
  cat <<'EOF'
gittan installer — https://gittan.sh

Usage:
  curl -fsSL https://gittan.sh/install | bash
  curl -fsSL https://gittan.sh/install | bash -s -- --dry-run
  curl -fsSL https://gittan.sh/install | bash -s -- --version 0.2.20

Options:
  --dry-run          Print what would happen; make no changes.
  --version VERSION  Install a specific PyPI version, e.g. 0.2.20.
  --help, -h         Show this help and exit.

The script does not read stdin, so piping from curl into bash is safe.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --version)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == -* || ! "$2" =~ ^[0-9] ]]; then
        printf '\033[1;31m !!\033[0m --version needs a version like 0.2.20, got: %s\n' "${2:-<none>}" >&2
        exit 2
      fi
      PIN_VERSION="$2"
      shift 2
      ;;
    --help|-h) print_help; exit 0 ;;
    *) echo "Unknown option: $1" >&2; echo "Run with --help for usage." >&2; exit 2 ;;
  esac
done

note() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m !!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m !!\033[0m %s\n' "$*" >&2; exit 1; }

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '   (dry-run) %s\n' "$*"
  else
    "$@"
  fi
}

# --- Python ---
if ! command -v python3 >/dev/null 2>&1; then
  die "Python 3 not found. Install Python ${PY_MIN_MAJOR}.${PY_MIN_MINOR}+ first: https://www.python.org/downloads/"
fi
PY_VERSION_OUTPUT="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "0.0")"
PY_MAJOR="${PY_VERSION_OUTPUT%%.*}"
PY_MINOR="${PY_VERSION_OUTPUT##*.}"
if [[ "$PY_MAJOR" -lt "$PY_MIN_MAJOR" ]] || { [[ "$PY_MAJOR" -eq "$PY_MIN_MAJOR" ]] && [[ "$PY_MINOR" -lt "$PY_MIN_MINOR" ]]; }; then
  die "Python ${PY_VERSION_OUTPUT} found, but Gittan needs ${PY_MIN_MAJOR}.${PY_MIN_MINOR}+. Upgrade: https://www.python.org/downloads/"
fi
note "Found Python ${PY_VERSION_OUTPUT}"

# --- install spec ---
INSTALL_SPEC="${PACKAGE}"
if [[ -n "$PIN_VERSION" ]]; then
  INSTALL_SPEC="${PACKAGE}==${PIN_VERSION}"
  note "Requested version: ${PIN_VERSION}"
fi

# --- pipx preferred ---
PIPX_CMD=()
if command -v pipx >/dev/null 2>&1; then
  PIPX_CMD=(pipx)
elif python3 -m pipx --version >/dev/null 2>&1; then
  PIPX_CMD=(python3 -m pipx)
fi

if [[ "${#PIPX_CMD[@]}" -gt 0 ]]; then
  note "Installing ${COMMAND} with pipx: ${PIPX_CMD[*]} install --force ${INSTALL_SPEC}"
  run "${PIPX_CMD[@]}" install --force "$INSTALL_SPEC"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    "${PIPX_CMD[@]}" ensurepath || true
  fi
else
  warn "pipx not found; falling back to 'pip install --user'."
  warn "For an isolated install with reliable PATH, install pipx: https://pypa.github.io/pipx/"
  if ! python3 -m pip --version >/dev/null 2>&1; then
    die "pip is unavailable for Python ${PY_VERSION_OUTPUT}. Install pip and retry, or use pipx."
  fi
  note "Installing ${COMMAND} with pip --user: python3 -m pip install --user --upgrade ${INSTALL_SPEC}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '   (dry-run) %s\n' "python3 -m pip install --user --upgrade $INSTALL_SPEC"
  else
    pip_out="$(python3 -m pip install --user --upgrade "$INSTALL_SPEC" 2>&1)" || {
      if printf '%s\n' "$pip_out" | grep -qi 'externally-managed-environment'; then
        die "pip refused to install: this Python is externally managed (PEP 668).
This is common on Debian/Ubuntu and Homebrew Python. Choose one:
  pipx (recommended):  https://pypa.github.io/pipx/
  virtualenv:          python3 -m venv .venv && source .venv/bin/activate && pip install ${INSTALL_SPEC}
  opt in explicitly:   python3 -m pip install --user --upgrade --break-system-packages ${INSTALL_SPEC}"
      fi
      printf '%s\n' "$pip_out" >&2
      die "pip install failed; see pip output above."
    }
  fi
fi

# --- confirm ---
note "Installed ${COMMAND}. Checking version…"
if command -v "$COMMAND" >/dev/null 2>&1; then
  "$COMMAND" -V || warn "${COMMAND} -V did not succeed."
else
  warn "${COMMAND} is not on PATH in this shell yet."
  warn "Open a new terminal (or run 'pipx ensurepath' and restart your shell), then: ${COMMAND} -V"
fi
echo
note "Docs: https://gittan.sh  ·  Run '${COMMAND} doctor' for setup hints."
note "Package: ${PYPI_BASE}/${PACKAGE}/"
