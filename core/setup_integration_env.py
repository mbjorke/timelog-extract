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
from typing import Any, Callable, Dict, List, Optional, Tuple

import questionary

from core.setup_shell_profile import shell_profile_path, upsert_export

# A verifier takes the collected env values and returns
# (ok, suspect_field_keys, human-readable detail). ``suspect_field_keys`` names
# the env vars most likely wrong so the caller can re-prompt just those.
Verifier = Callable[[Dict[str, str]], Tuple[bool, List[str], str]]


@dataclass(frozen=True)
class CredField:
    """One environment variable that an integration needs."""

    env_key: str
    prompt: str
    secret: bool = False


def _prompt_value(field: CredField) -> str:
    # Input is shown (questionary.text) for all fields, including secrets, so the
    # user can see exactly what was pasted; secrets are guarded by a confirmation
    # and live verification rather than by hiding the characters.
    try:
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
    verify: Optional[Verifier] = None,
) -> Tuple[str, str, List[str]]:
    """
    Optionally bootstrap an integration's credential env vars.

    Returns ``(status, note, next_steps)`` mirroring
    ``configure_github_env_for_setup``. Values already present in the
    environment are kept as-is and never re-written. In ``--yes`` mode nothing
    is prompted (non-interactive), so missing values stay unset.

    When ``verify`` is provided and a full set of values is collected, the
    credentials are checked against the provider API **before** anything is
    written; on failure nothing is persisted and ``ACTION_REQUIRED`` is returned.
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
            # Input is visible, and credentials are checked live before saving,
            # so there is no separate "is this correct?" confirmation step.
            values[field.env_key] = _prompt_value(field)

    if not any(values.values()):
        return "ACTION_REQUIRED", f"{label} credentials still unset after setup attempt.", [enable_hint]

    # Verify before persisting, and let the user correct the suspect field(s) in
    # place: only a complete, working credential set is ever saved.
    if verify is not None and all(values.get(f.env_key) for f in fields):
        field_by_key = {f.env_key: f for f in fields}
        while True:
            ok, suspect_keys, detail = verify(values)
            if ok:
                console.print(f"[green]✓[/green] {label} verified — {detail}.")
                break
            to_fix = [k for k in (suspect_keys or list(field_by_key)) if k in field_by_key]
            console.print(
                f"[red]✗[/red] {label} verification failed — {detail}. "
                f"Re-enter {', '.join(to_fix)} (blank to cancel):"
            )
            changed = False
            for key in to_fix:
                new_value = _prompt_value(field_by_key[key])
                if new_value:
                    values[key] = new_value
                    changed = True
            if not changed:
                console.print(f"[red]✗[/red] {label} not verified — nothing was written.")
                return (
                    "ACTION_REQUIRED",
                    f"{label} credential verification failed: {detail}",
                    [enable_hint],
                )

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


def _verify_jira(values: Dict[str, str]) -> Tuple[bool, List[str], str]:
    from collectors.jira import JiraCredentials, verify_jira_credentials

    creds = JiraCredentials(
        base_url=str(values["JIRA_BASE_URL"]).rstrip("/"),
        email=values["JIRA_EMAIL"],
        api_token=values["JIRA_API_TOKEN"],
    )
    ok, detail, suspect = verify_jira_credentials(creds)
    suspect_fields = {
        "url": ["JIRA_BASE_URL"],
        "credentials": ["JIRA_EMAIL", "JIRA_API_TOKEN"],
    }.get(suspect, [])
    return ok, suspect_fields, detail


def _verify_toggl(values: Dict[str, str]) -> Tuple[bool, List[str], str]:
    from collectors.toggl import TogglCredentials, verify_toggl_credentials

    try:
        workspace_id = int(str(values["TOGGL_WORKSPACE_ID"]).strip())
    except (KeyError, ValueError):
        return False, ["TOGGL_WORKSPACE_ID"], "workspace id must be a number"
    creds = TogglCredentials(api_token=values["TOGGL_API_TOKEN"], workspace_id=workspace_id)
    ok, detail, suspect = verify_toggl_credentials(creds)
    suspect_fields = {"credentials": ["TOGGL_API_TOKEN"]}.get(suspect, [])
    return ok, suspect_fields, detail


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
        verify=_verify_jira,
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
        verify=_verify_toggl,
    )
