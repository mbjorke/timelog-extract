"""Setup helpers for Jira + Toggl credential env bootstrap.

Mirrors `core/setup_github_env.py` but is data-driven: each integration is a
list of env fields. Persists chosen values to the user's shell profile via the
shared `setup_shell_profile` helpers, so onboarding is consistent across
GitHub, Jira, and Toggl. Existing env vars always take precedence and are never
overwritten.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Tuple

import questionary

from core.setup_shell_profile import shell_profile_path, upsert_export


@dataclass(frozen=True)
class CredField:
    """One environment variable that an integration needs."""

    env_key: str
    prompt: str
    secret: bool = False


def _prompt_value(field: CredField) -> str:
    try:
        if field.secret:
            return (questionary.password(f"Paste {field.env_key} (input hidden):").ask() or "").strip()
        return (questionary.text(f"{field.prompt}:").ask() or "").strip()
    except EOFError:
        # Non-interactive stdin (piped/CI): treat as no input.
        return ""


def _confirm(prompt: str, *, default: bool) -> bool:
    try:
        return bool(questionary.confirm(prompt, default=default).ask())
    except EOFError:
        return False


def configure_env_credentials(
    console: Any,
    *,
    label: str,
    fields: List[CredField],
    enable_hint: str,
    verify_cmd: str,
    yes: bool,
    dry_run: bool,
    default_enable: bool = False,
) -> Tuple[str, str, List[str]]:
    """
    Optionally bootstrap an integration's credential env vars.

    Returns ``(status, note, next_steps)`` mirroring
    ``configure_github_env_for_setup``. Values already present in the
    environment are kept as-is and never re-written. In ``--yes`` mode nothing
    is prompted (non-interactive), so missing values stay unset.
    """
    existing = {f.env_key: (os.environ.get(f.env_key) or "").strip() for f in fields}
    if all(existing.values()):
        return "PASS", f"{label} credentials already set.", []

    if yes:
        # Non-interactive: cannot prompt for secrets; surface the manual hint.
        return "SKIPPED", f"{label} credentials not set (skipped in --yes mode).", [enable_hint]

    if not _confirm(f"Configure {label} credentials now?", default=default_enable):
        return "SKIPPED", f"User skipped {label} credential bootstrap.", [enable_hint]

    profile = shell_profile_path()
    values = dict(existing)
    for field in fields:
        if not values[field.env_key]:
            values[field.env_key] = _prompt_value(field)

    if not any(values.values()):
        return "ACTION_REQUIRED", f"{label} credentials still unset after setup attempt.", [enable_hint]

    secret_warned = False
    changed_parts: List[str] = []
    for field in fields:
        value = values.get(field.env_key, "")
        if not value or value == existing.get(field.env_key):
            continue
        if field.secret and not secret_warned:
            console.print(
                f"[yellow]Note:[/yellow] {label} secrets will be written to "
                f"{profile.name} as plaintext."
            )
            secret_warned = True
        upsert_export(profile, field.env_key, value, dry_run=dry_run)
        changed_parts.append(field.env_key)

    all_set = all(values.get(f.env_key) for f in fields)
    status = "PASS" if all_set else "ACTION_REQUIRED"
    changed_note = ", ".join(changed_parts) if changed_parts else "no file changes"
    if dry_run:
        note = f"[dry-run] would update {changed_note} in {profile.name}."
    else:
        note = f"{label} env bootstrap: {changed_note}; profile={profile.name}."

    steps: List[str] = []
    if changed_parts:
        steps.append(f"Reload shell profile (`source {profile}`) and run `{verify_cmd}`.")
    if not all_set:
        steps.append(enable_hint)
    elif not steps:
        steps.append(f"Run `{verify_cmd}` to verify.")
    return status, note, steps


JIRA_FIELDS = [
    CredField("JIRA_BASE_URL", "Jira base URL (e.g. https://you.atlassian.net)"),
    CredField("JIRA_EMAIL", "Jira account email"),
    CredField("JIRA_API_TOKEN", "Jira API token", secret=True),
]

TOGGL_FIELDS = [
    CredField("TOGGL_API_TOKEN", "Toggl API token", secret=True),
    CredField("TOGGL_WORKSPACE_ID", "Toggl workspace id (numeric)"),
]


def configure_jira_env_for_setup(
    console: Any, *, yes: bool, dry_run: bool, default_enable: bool = False
) -> Tuple[str, str, List[str]]:
    """Bootstrap Jira worklog-sync credentials."""
    return configure_env_credentials(
        console,
        label="Jira",
        fields=JIRA_FIELDS,
        enable_hint=(
            "Optional: set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN to enable "
            "`gittan jira-sync`."
        ),
        verify_cmd="gittan doctor --jira-sync auto",
        yes=yes,
        dry_run=dry_run,
        default_enable=default_enable,
    )


def configure_toggl_env_for_setup(
    console: Any, *, yes: bool, dry_run: bool, default_enable: bool = False
) -> Tuple[str, str, List[str]]:
    """Bootstrap Toggl time-entry-sync credentials."""
    return configure_env_credentials(
        console,
        label="Toggl",
        fields=TOGGL_FIELDS,
        enable_hint=(
            "Optional: set TOGGL_API_TOKEN and TOGGL_WORKSPACE_ID to enable "
            "`gittan toggl-sync`."
        ),
        verify_cmd="gittan doctor",
        yes=yes,
        dry_run=dry_run,
        default_enable=default_enable,
    )
