"""Setup helper for GitHub env bootstrap (GITHUB_USER / GITHUB_TOKEN)."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import questionary


def _shell_profile_path() -> Path:
    shell = (os.environ.get("SHELL") or "").lower()
    home = Path.home()
    if "zsh" in shell:
        return home / ".zshrc"
    if "bash" in shell:
        return home / ".bashrc"
    return home / ".profile"


def _upsert_export(path: Path, key: str, value: str, *, dry_run: bool) -> bool:
    line = f"export {key}={shlex.quote(value)}"
    if dry_run:
        return True
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    rows = existing.splitlines()
    prefix = f"export {key}="
    changed = False
    found = False
    out: list[str] = []
    for row in rows:
        if row.strip().startswith(prefix):
            out.append(line)
            found = True
            changed = True
        else:
            out.append(row)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(line)
        changed = True
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return changed


def _gh_read_token() -> str:
    if not shutil.which("gh"):
        return ""
    cp = subprocess.run(["gh", "auth", "token"], check=False, capture_output=True, text=True)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def _gh_read_user() -> str:
    if not shutil.which("gh"):
        return ""
    cp = subprocess.run(["gh", "api", "user", "--jq", ".login"], check=False, capture_output=True, text=True)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def configure_github_env_for_setup(console: Any, *, yes: bool, dry_run: bool) -> tuple[str, str, list[str]]:
    """Optionally bootstrap GitHub env vars for better source reliability."""
    existing_user = (os.environ.get("GITHUB_USER") or "").strip()
    existing_token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    if existing_user and existing_token:
        return "PASS", "GITHUB_USER and GITHUB_TOKEN already set.", []

    if not yes:
        if not questionary.confirm("Configure GitHub env vars for source reliability now?", default=True).ask():
            return "SKIPPED", "User skipped GitHub env bootstrap.", ["Optional: set GITHUB_USER/GITHUB_TOKEN for GitHub source stability."]

    profile = _shell_profile_path()
    user = existing_user
    token = existing_token
    mode = "existing"
    if not token:
        if yes or questionary.confirm("Use GitHub CLI auth (`gh auth token`) if available?", default=True).ask():
            token = _gh_read_token()
            if not user:
                user = _gh_read_user()
            mode = "gh"
    if not user and not yes:
        user = (questionary.text("GitHub username (for public events):").ask() or "").strip()
        if user:
            mode = "manual"
    if not token and not yes:
        token = (questionary.password("Paste GITHUB_TOKEN (input hidden, optional):").ask() or "").strip()
        if token:
            mode = "manual"

    if not user and not token:
        return "ACTION_REQUIRED", "GitHub env vars still unset after setup attempt.", ["Set GITHUB_USER and optionally GITHUB_TOKEN, then rerun `gittan doctor`."]

    changed_parts: list[str] = []
    if user and (not existing_user or user != existing_user):
        _upsert_export(profile, "GITHUB_USER", user, dry_run=dry_run)
        changed_parts.append("GITHUB_USER")
    if token and (not existing_token or token != existing_token):
        _upsert_export(profile, "GITHUB_TOKEN", token, dry_run=dry_run)
        changed_parts.append("GITHUB_TOKEN")

    reload_hint = f"source {profile}"
    changed_note = ", ".join(changed_parts) if changed_parts else "no file changes"
    note = f"GitHub env bootstrap ({mode}): {changed_note}; profile={profile.name}."
    steps = [f"Reload shell profile (`{reload_hint}`) and run `gittan doctor --github-source auto`."]
    status = "PASS" if (user or token) else "ACTION_REQUIRED"
    if dry_run:
        note = f"[dry-run] would update {changed_note or 'GitHub env vars'} in {profile.name}."
    return status, note, steps

