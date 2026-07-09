"""Shared next-step guidance for onboarding-oriented CLI commands."""

from __future__ import annotations

from pathlib import Path

from core.config import load_projects_config_payload
from core.projects_lint import lint_projects_payload

PROJECT_STATUS_PASS = "PASS"
PROJECT_STATUS_FAIL = "FAIL"
PROJECT_STATUS_SKIPPED = "SKIPPED"
PROJECT_STATUS_ACTION_REQUIRED = "ACTION_REQUIRED"

_RULE_HYGIENE_LINT_CODES = frozenset(
    {
        "broad-tracked-url",
        "broad-term",
        "overlap-term",
        "repo-path-overlap",
        "slug-customer-conflict",
        "thin-slug-duplicate",
    }
)


def rule_hygiene_needed_for_config(config_path: Path, *, git_coverage_warn: bool = False) -> bool:
    """True when config lint or git match_terms coverage suggests review/audit next steps."""
    if git_coverage_warn:
        return True
    if not config_path.exists():
        return False
    try:
        payload = load_projects_config_payload(config_path)
    except Exception:
        return False
    return any(w.code in _RULE_HYGIENE_LINT_CODES for w in lint_projects_payload(payload))


def build_doctor_next_steps(
    *,
    cli_on_path: bool,
    projects_config_ok: bool,
    config_valid: bool,
    worklog_ok: bool,
    match_terms_ok: bool = True,
    rule_hygiene_needed: bool = False,
    config_path: Path,
    worklog_path: Path,
) -> list[str]:
    steps: list[str] = []
    if not projects_config_ok:
        if cli_on_path:
            steps.append(
                "Run `gittan setup --dry-run` first to preview the resolved config path and "
                "repo seeds — doctor does not write config."
            )
            steps.append("When the preview looks right, run `gittan setup` to create the project config.")
        else:
            steps.append(
                f"Create `{config_path.name}` in this repository with at least one enabled project profile."
            )
    elif not config_valid:
        if cli_on_path:
            steps.append(
                f"`{config_path.name}` exists but is not valid project config — run "
                "`gittan setup --dry-run` to preview repair; doctor did not change it."
            )
            steps.append(
                "To repair with a timestamped backup before replacement, run `gittan setup`."
            )
        else:
            steps.append(
                f"Repair `{config_path.name}` manually or install the CLI and run `gittan setup --dry-run`."
            )
    if rule_hygiene_needed or not match_terms_ok:
        review = "Run `gittan review` to map URL domains to the right project buckets."
        audit = (
            "Run `gittan projects-audit` to audit match_terms and tracked_urls hit rates "
            "before trimming stale rules."
        )
        if review not in steps:
            steps.append(review)
        if audit not in steps:
            steps.append(audit)
    if not worklog_ok:
        steps.append(
            f"Create the expected worklog file at `{worklog_path}` (legacy fallback may resolve to "
            f"`TIMELOG.md`) or set a top-level `worklog` in `timelog_projects.json` and/or per-project "
            f"`worklog` paths in `timelog_projects.json`."
        )
    if not cli_on_path:
        steps.append("Run `pipx ensurepath`, reload your shell, then rerun `gittan doctor`.")
    if not steps:
        steps.append("Run `gittan report --today --source-summary` for a first local report.")
        steps.append("Use `gittan projects` if you want to refine project matching before reporting.")
    return steps


def build_setup_next_steps(
    *,
    dry_run: bool,
    projects_status: str,
    mapping_status: str,
    doctor_status: str,
    smoke_status: str,
    fast: bool = False,
    has_project_buckets: bool = False,
    merge_skipped: bool = False,
) -> list[str]:
    steps: list[str] = []
    if dry_run:
        setup_cmd = "gittan setup --fast" if fast else "gittan setup"
        if merge_skipped:
            steps.append(
                f"Next: run `{setup_cmd}` without `--dry-run` for non-destructive apply "
                "(existing project config is not merge-written unless you add `--bootstrap-repos`)."
            )
        else:
            steps.append(f"Next: run `{setup_cmd}` without `--dry-run` when you are ready to apply setup.")
        if has_project_buckets:
            steps.append("Then: run `gittan review` to map URL domains to project buckets.")
            steps.append("Optional: `gittan review --json` for read-only URL candidates (agents/scripts).")
        steps.append("Then: run `gittan report --today --source-summary` for your first real report.")
        steps.append("Optional: run `gittan setup-global-timelog` if you want machine-wide commit-to-worklog automation.")
        return steps

    if doctor_status == PROJECT_STATUS_ACTION_REQUIRED:
        steps.append("Next: rerun `gittan doctor` and resolve any missing PATH, permission, or source hints.")
    if projects_status == PROJECT_STATUS_FAIL:
        steps.append("Then: run `gittan projects` to repair project entries, then verify `match_terms` and worklog path.")
    if projects_status in {PROJECT_STATUS_SKIPPED, PROJECT_STATUS_ACTION_REQUIRED}:
        steps.append("Then: use `gittan projects` to review project names, `match_terms`, and worklog path.")
    if mapping_status in {PROJECT_STATUS_SKIPPED, PROJECT_STATUS_ACTION_REQUIRED}:
        steps.append(
            "Then: run `gittan setup` again and complete the project mapping step so reports classify work to the right project."
        )
    if smoke_status in {PROJECT_STATUS_FAIL, PROJECT_STATUS_ACTION_REQUIRED, PROJECT_STATUS_SKIPPED}:
        steps.append("Then: run `gittan report --today --source-summary` to confirm you get a useful local report.")
    if not steps:
        if has_project_buckets:
            steps.append("Next: run `gittan review` to map URL domains to project buckets.")
            steps.append("Optional: `gittan review --json` for read-only URL mapping candidates.")
            steps.append("Then: run `gittan report --today --source-summary` for your first report.")
        else:
            steps.append("Next: run `gittan report --today --source-summary` for your first report.")
            steps.append("Optional: use `gittan projects` later if you want to refine project matching.")
    if fast:
        steps.append("Optional later: run `gittan setup-global-timelog` when you want machine-wide commit-to-worklog automation.")
    return steps


def _projects_config_resolved(config_path: Path) -> bool:
    if not config_path.exists():
        return False
    try:
        load_projects_config_payload(config_path)
        return True
    except Exception:
        return False


def build_review_next_steps(
    *,
    config_resolved: bool,
    has_candidates: bool,
    uncategorized: bool = False,
) -> list[str]:
    """Advisory project-config follow-ups after interactive ``gittan review``."""
    steps: list[str] = []
    if not config_resolved:
        steps.append(
            "Run `gittan setup --dry-run` to preview the resolved projects config path before mapping."
        )
        steps.append("Run `gittan projects` to inspect or repair project profiles (read-only until you apply).")
        return steps
    if has_candidates:
        if uncategorized:
            steps.append(
                "Use `gittan map` to attach git repos / working dirs to an existing "
                "customer/line (branch/session-title hits are context — not permanent "
                "match_terms)."
            )
        steps.append(
            "Run `gittan projects-audit` to check match_terms and tracked_urls hit rates before trimming rules."
        )
        steps.append("Use `gittan projects` to refine profiles for projects you assigned during review.")
    else:
        steps.append(
            "Run `gittan projects-audit` to find zero-hit rules or unanchored signals for this date window."
        )
        steps.append("Run `gittan report --today --source-summary` to confirm classification looks right.")
    return steps


def finish_review_guidance(
    console,
    *,
    projects_config: str | Path,
    has_candidates: bool,
    uncategorized: bool = False,
) -> None:
    """Print deduped review next steps (terminal-only; never mutates config)."""
    path = Path(projects_config).expanduser()
    steps = build_review_next_steps(
        config_resolved=_projects_config_resolved(path),
        has_candidates=has_candidates,
        uncategorized=uncategorized,
    )
    print_next_steps(console, list(dict.fromkeys(steps)))


def print_next_steps(console, steps: list[str]) -> None:
    from outputs.terminal_theme import STYLE_LABEL, STYLE_MUTED

    console.print(f"[{STYLE_LABEL}]Next steps[/{STYLE_LABEL}]")
    for step in steps:
        console.print(f"[{STYLE_MUTED}]- {step}[/{STYLE_MUTED}]")
