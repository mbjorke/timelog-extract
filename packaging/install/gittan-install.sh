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
#   curl -fsSL https://gittan.sh/install | bash -s -- --version 0.4.0
#   curl -fsSL https://gittan.sh/install | bash -s -- --no-fix-shadow
#   curl -fsSL https://gittan.sh/install | bash -s -- --help
#
# What it does:
#   - verifies Python 3.10+ is available
#   - installs gittan via pipx (preferred) or `pip install --user` as a fallback
#   - prints `gittan -V` to confirm
#   - by default uninstalls other timelog-extract copies that would shadow PATH
#     (Anaconda / old pip --user); use --no-fix-shadow to keep them
#
# The script does not read stdin, so piping from curl into bash is safe.
set -euo pipefail

PACKAGE="timelog-extract"   # PyPI package name
COMMAND="gittan"            # CLI command this puts on your PATH
PY_MIN_MAJOR=3
PY_MIN_MINOR=10
PYPI_BASE="https://pypi.org/project"
INSTALL_URL="https://gittan.sh/install"

DRY_RUN=0
PIN_VERSION=""
FIX_SHADOW=1

print_help() {
  cat <<'EOF'
gittan installer — https://gittan.sh

Usage:
  curl -fsSL https://gittan.sh/install | bash
  curl -fsSL https://gittan.sh/install | bash -s -- --dry-run
  curl -fsSL https://gittan.sh/install | bash -s -- --version 0.4.0
  curl -fsSL https://gittan.sh/install | bash -s -- --no-fix-shadow

Options:
  --dry-run            Print what would happen; make no changes.
  --version VERSION    Install a specific PyPI version, e.g. 0.4.0.
  --fix-shadow        Default: uninstall other timelog-extract copies that
                       shadow the fresh binary on PATH (Anaconda / old pip).
  --no-fix-shadow     Keep other installs; only warn if PATH still shadows.
  --help, -h           Show this help and exit.

Do not use plain `pip install -U timelog-extract` on an old Python: pip will
silently install the newest release that Python still supports (e.g. 0.3.0 on
3.9) instead of current. Prefer this installer or pipx on Python 3.10+.

The script does not read stdin, so piping from curl into bash is safe.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --fix-shadow) FIX_SHADOW=1; shift ;;
    --no-fix-shadow) FIX_SHADOW=0; shift ;;
    --version)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == -* || ! "$2" =~ ^[0-9] ]]; then
        printf '\033[1;31m !!\033[0m --version needs a version like 0.4.0, got: %s\n' "${2:-<none>}" >&2
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

same_path() {
  python3 -c 'import os,sys; print("yes" if os.path.realpath(sys.argv[1])==os.path.realpath(sys.argv[2]) else "no")' "$1" "$2" 2>/dev/null || echo no
}

# List every gittan on PATH (first wins for a plain `gittan` invocation).
list_command_on_path() {
  local name="$1"
  local -a seen=()
  local dir candidate real already s
  local old_ifs="$IFS"
  IFS=':'
  # shellcheck disable=SC2086
  for dir in $PATH; do
    IFS="$old_ifs"
    [[ -z "$dir" ]] && continue
    candidate="${dir%/}/${name}"
    [[ -x "$candidate" || -f "$candidate" ]] || continue
    real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$candidate" 2>/dev/null || echo "$candidate")"
    already=0
    for s in "${seen[@]+"${seen[@]}"}"; do
      if [[ "$s" == "$real" ]]; then already=1; break; fi
    done
    [[ "$already" -eq 1 ]] && continue
    seen+=("$real")
    printf '%s\n' "$candidate"
  done
  IFS="$old_ifs"
}

# Best-effort: uninstall timelog-extract via the Python that owns a console script.
owner_python_for_script() {
  local bin="$1"
  local shebang first rest sibling
  shebang="$(head -n 1 "$bin" 2>/dev/null || true)"
  if [[ "$shebang" == "#!"* ]]; then
    first="${shebang:2}"
    first="${first%%[[:space:]]*}"
    rest="${shebang#*[[:space:]]}"
    if [[ "$(basename "$first")" == "env" && "$rest" != "$shebang" ]]; then
      printf '%s\n' "${rest%%[[:space:]]*}"
      return 0
    fi
    if [[ -x "$first" ]]; then
      printf '%s\n' "$first"
      return 0
    fi
  fi
  sibling="$(dirname "$bin")/python"
  if [[ -x "$sibling" ]]; then
    printf '%s\n' "$sibling"
    return 0
  fi
  sibling="$(dirname "$bin")/python3"
  if [[ -x "$sibling" ]]; then
    printf '%s\n' "$sibling"
    return 0
  fi
  return 1
}

uninstall_via_script() {
  local bin="$1"
  local owner
  if ! owner="$(owner_python_for_script "$bin")"; then
    warn "Could not find Python that owns ${bin}; skip uninstall."
    return 1
  fi
  note "Uninstalling ${PACKAGE} via ${owner} (was shadowing at ${bin})"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '   (dry-run) %s -m pip uninstall -y %s\n' "$owner" "$PACKAGE"
    return 0
  fi
  "$owner" -m pip uninstall -y "$PACKAGE" 2>/dev/null || {
    warn "pip uninstall via ${owner} failed — remove ${bin} manually if it still shadows."
    return 1
  }
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

# --- existing install? (re-running the installer is a supported upgrade path) ---
EXISTING_BIN="$(command -v "$COMMAND" 2>/dev/null || true)"
EXISTING_VERSION=""
if [[ -n "$EXISTING_BIN" ]]; then
  EXISTING_VERSION="$("$EXISTING_BIN" -V 2>/dev/null | awk '{print $NF}' || true)"
  note "Found existing ${COMMAND}${EXISTING_VERSION:+ ${EXISTING_VERSION}} at ${EXISTING_BIN} — upgrading (reinstall)."
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

# Check the binary this run installed — not whatever PATH resolves first. An
# older install earlier in PATH otherwise answers here and reports a stale
# version right after a successful upgrade (gittan-home#8).
INSTALLED_BIN=""
if [[ "${#PIPX_CMD[@]}" -gt 0 ]]; then
  pipx_bin_dir="$("${PIPX_CMD[@]}" environment --value PIPX_BIN_DIR 2>/dev/null || true)"
  INSTALLED_BIN="${pipx_bin_dir:-${PIPX_BIN_DIR:-$HOME/.local/bin}}/${COMMAND}"
else
  user_base="$(python3 -m site --user-base 2>/dev/null || true)"
  [[ -n "$user_base" ]] && INSTALLED_BIN="${user_base}/bin/${COMMAND}"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '   (dry-run) %s\n' "${INSTALLED_BIN:-$COMMAND} -V"
  if [[ "$FIX_SHADOW" -eq 1 ]]; then
    printf '   (dry-run) would uninstall PATH shadows of %s\n' "$COMMAND"
  fi
elif [[ -n "$INSTALLED_BIN" && -x "$INSTALLED_BIN" ]]; then
  "$INSTALLED_BIN" -V || warn "${COMMAND} -V did not succeed."
  NEW_VERSION="$("$INSTALLED_BIN" -V 2>/dev/null | awk '{print $NF}' || true)"
  if [[ -n "$EXISTING_VERSION" && -n "$NEW_VERSION" ]]; then
    if [[ "$EXISTING_VERSION" != "$NEW_VERSION" ]]; then
      note "Upgraded ${COMMAND} ${EXISTING_VERSION} → ${NEW_VERSION}"
    else
      note "Reinstalled ${COMMAND} (already at ${NEW_VERSION})."
    fi
  fi

  # Optional: remove other timelog-extract installs that win on PATH.
  if [[ "$FIX_SHADOW" -eq 1 ]]; then
    while IFS= read -r other; do
      [[ -z "$other" ]] && continue
      if [[ "$(same_path "$other" "$INSTALLED_BIN")" == "yes" ]]; then
        continue
      fi
      uninstall_via_script "$other" || true
    done < <(list_command_on_path "$COMMAND")
    hash -r 2>/dev/null || true
  fi

  RESOLVED="$(command -v "$COMMAND" 2>/dev/null || true)"
  SAME="no"
  if [[ -n "$RESOLVED" ]]; then
    SAME="$(same_path "$RESOLVED" "$INSTALLED_BIN")"
  fi
  if [[ -n "$RESOLVED" && "$SAME" != "yes" ]]; then
    OLD_VER="$("$RESOLVED" -V 2>/dev/null | awk '{print $NF}' || true)"
    warn "Your shell resolves '${COMMAND}' to ${RESOLVED}${OLD_VER:+ (${OLD_VER})} — that OLDER install shadows the one just installed (${INSTALLED_BIN}${NEW_VERSION:+ (${NEW_VERSION})})."
    if [[ "$FIX_SHADOW" -eq 0 ]]; then
      warn "Re-run without --no-fix-shadow (default cleans this up), or manually:"
    else
      warn "Automatic cleanup did not clear PATH. Manually:"
    fi
    warn "  $(dirname "$RESOLVED")/python -m pip uninstall -y ${PACKAGE}   # if that python exists"
    warn "Then:  hash -r && ${COMMAND} -V"
    # --no-fix-shadow is documented as warn-only: the user asked us to leave the
    # competing install alone, so a shadowed PATH is the outcome they chose, not
    # a failed install. Exiting non-zero there would break scripted opt-outs.
    # The default path did try to clear the shadow, so still finding one means
    # the cleanup did not work and that is a real error.
    if [[ "$FIX_SHADOW" -eq 1 ]]; then
      die "Install succeeded, but PATH still shadows the new ${COMMAND}."
    fi
  fi
elif command -v "$COMMAND" >/dev/null 2>&1; then
  "$COMMAND" -V || warn "${COMMAND} -V did not succeed."
else
  warn "${COMMAND} is not on PATH in this shell yet."
  warn "Open a new terminal (or run 'pipx ensurepath' and restart your shell), then: ${COMMAND} -V"
fi
echo
note "Docs: https://gittan.sh  ·  Run '${COMMAND} doctor' for setup hints."
note "Package: ${PYPI_BASE}/${PACKAGE}/"
