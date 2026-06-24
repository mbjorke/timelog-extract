"""Configuration/profile normalization utilities."""

from __future__ import annotations

import getpass
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECTS_CONFIG_FILENAME = "timelog_projects.json"
ENV_PROJECTS_CONFIG = "GITTAN_PROJECTS_CONFIG"
ENV_GITTAN_HOME = "GITTAN_HOME"
SOURCE_GITTAN_HOME = "gittan_home"
SOURCE_PROFILE_HOME = "profile_home"
# Back-compat alias for callers/tests that still mention the old name.
SOURCE_LEGACY_HOME = SOURCE_GITTAN_HOME


def canonical_gittan_home() -> Path:
    """Machine-wide Gittan state directory (config + worklogs)."""
    return Path.home() / ".gittan"


def canonical_projects_config_path() -> Path:
    """Default projects config file under :func:`canonical_gittan_home`."""
    return canonical_gittan_home() / PROJECTS_CONFIG_FILENAME


def _default_profile_home() -> Path:
    """Per-user profile directory used when the canonical Gittan home file is absent."""
    user = (os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser() or "user").strip().lower()
    safe = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in user).strip("-_") or "user"
    return Path.home() / f".gittan-{safe}"


def resolve_projects_config_path_and_source(cwd: Optional[Path] = None) -> tuple[Path, str]:
    """Resolve the active projects config path with source metadata.

    Resolution is intentionally independent of the current working directory.
    Use ``--projects-config`` (or ``GITTAN_PROJECTS_CONFIG``) for deliberate
    per-run overrides such as demos or sandboxes.
    """
    _ = cwd  # reserved for shadow-detection helpers; not used for resolution.
    configured = str(os.environ.get(ENV_PROJECTS_CONFIG, "")).strip()
    if configured:
        return Path(configured).expanduser(), ENV_PROJECTS_CONFIG
    gittan_home = str(os.environ.get(ENV_GITTAN_HOME, "")).strip()
    if gittan_home:
        return Path(gittan_home).expanduser() / PROJECTS_CONFIG_FILENAME, ENV_GITTAN_HOME
    canonical = canonical_projects_config_path()
    if canonical.is_file():
        return canonical, SOURCE_GITTAN_HOME
    profile_home = _default_profile_home() / PROJECTS_CONFIG_FILENAME
    if profile_home.is_file():
        return profile_home, SOURCE_PROFILE_HOME
    return canonical, SOURCE_GITTAN_HOME


def find_ignored_projects_config_paths(
    resolved_path: Path,
    *,
    cwd: Optional[Path] = None,
) -> list[tuple[Path, str]]:
    """Return other timelog_projects.json files that exist but are not active."""
    resolved = resolved_path.expanduser().resolve()
    seen: set[Path] = set()
    ignored: list[tuple[Path, str]] = []
    cwd_path = (cwd if cwd is not None else Path.cwd()).resolve()
    candidates = [
        (Path.home() / PROJECTS_CONFIG_FILENAME, "home directory"),
        (cwd_path / PROJECTS_CONFIG_FILENAME, "current working directory"),
        (_default_profile_home() / PROJECTS_CONFIG_FILENAME, "profile home"),
    ]
    for path, label in candidates:
        candidate = path.expanduser().resolve()
        if candidate in seen or candidate == resolved or not candidate.is_file():
            continue
        seen.add(candidate)
        ignored.append((candidate, label))
    return ignored


def find_legacy_home_worklog_profiles(profiles, config_path: Optional[Path]) -> list[str]:
    """Profile names whose worklog still points at ~/worklogs while config is under ~/.gittan."""
    if config_path is None:
        return []
    cfg = Path(config_path).expanduser().resolve()
    if cfg.parent != canonical_gittan_home().resolve():
        return []
    legacy_root = (Path.home() / "worklogs").resolve()
    names: list[str] = []
    for profile in profiles or []:
        raw = str((profile or {}).get("worklog", "")).strip()
        name = str((profile or {}).get("name", "")).strip()
        if not raw or not name:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (cfg.parent / path).resolve()
        else:
            path = path.resolve()
        if path.parent == legacy_root:
            names.append(name)
    return sorted(names)


def projects_config_resolution_warnings(
    resolved_path: Path,
    *,
    cwd: Optional[Path] = None,
    profiles: Optional[list] = None,
) -> list[str]:
    """Human-readable warnings when shadow configs or worklog dirs are in use."""
    resolved = resolved_path.expanduser().resolve()
    warnings: list[str] = []
    for path, label in find_ignored_projects_config_paths(resolved, cwd=cwd):
        warnings.append(
            f"Ignoring {path} ({label}). Active config: {resolved}. "
            "Archive or remove the unused copy, or pass --projects-config for a deliberate override."
        )
    legacy_worklogs = find_legacy_home_worklog_profiles(profiles or [], resolved)
    if legacy_worklogs:
        sample = ", ".join(legacy_worklogs[:4])
        if len(legacy_worklogs) > 4:
            sample = f"{sample}, …"
        warnings.append(
            f"{len(legacy_worklogs)} project(s) still point at ~/worklogs/ ({sample}). "
            f"Canonical worklogs live under {canonical_gittan_home() / 'worklogs'}/."
        )
    return warnings


def resolve_projects_config_path(cwd: Optional[Path] = None) -> Path:
    """Resolve the default projects-config path from env or workspace."""
    resolved, _source = resolve_projects_config_path_and_source(cwd=cwd)
    return resolved


def default_projects_config_option() -> str:
    """Default CLI value for --projects-config style options.

    Typer evaluates function signature defaults when command modules are
    imported, so commands using this helper capture the environment from import
    time unless they call it explicitly at runtime.
    """
    return str(resolve_projects_config_path())


def as_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def normalize_profile(raw):
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("Each project profile must have 'name'")
    if "match_terms" in raw:
        match_terms_input = as_list(raw.get("match_terms"))
    else:
        match_terms_input = [name]
    tracked_urls = as_list(raw.get("tracked_urls"))
    email = str(raw.get("email", "")).strip()
    customer = str(raw.get("customer", "")).strip() or name
    project_id = str(raw.get("project_id", "")).strip() or name
    ticket_mode = str(raw.get("ticket_mode", "")).strip().lower() or "optional"
    if ticket_mode not in {"required", "optional", "none"}:
        raise ValueError("ticket_mode must be one of: required, optional, none")
    default_client = str(raw.get("default_client", "")).strip() or customer
    invoice_title = str(raw.get("invoice_title", "")).strip()
    invoice_description = str(raw.get("invoice_description", "")).strip()
    enabled = bool(raw.get("enabled", True))
    canonical_project = str(raw.get("canonical_project", "")).strip() or name
    aliases = as_list(raw.get("aliases"))
    merged_aliases = sorted({alias for alias in aliases + [name, canonical_project] if alias})
    terms_set = {t.lower() for t in match_terms_input if t}
    # Legacy behavior: project name is always matchable when match_terms is absent or non-empty.
    # Explicit `match_terms: []` stays empty (advanced / intentional opt-out).
    if match_terms_input and name.lower() not in terms_set:
        terms_set.add(name.lower())
    terms = sorted(terms_set)
    merged_tracked_urls = sorted({url for url in tracked_urls if url})
    tags = sorted({str(t).strip().lower() for t in as_list(raw.get("tags")) if str(t).strip()})
    profile = {
        "name": name,
        "project_id": project_id,
        "enabled": enabled,
        "ticket_mode": ticket_mode,
        "default_client": default_client,
        "match_terms": terms,
        "tracked_urls": merged_tracked_urls,
        "canonical_project": canonical_project,
        "aliases": merged_aliases,
        "email": email,
        "customer": customer,
        "invoice_title": invoice_title,
        "invoice_description": invoice_description,
        "tags": tags,
    }
    worklog = str(raw.get("worklog", "")).strip()
    if worklog:
        profile["worklog"] = worklog
    toggl_project_id = raw.get("toggl_project_id")
    if toggl_project_id not in (None, ""):
        # bool is an int subclass; reject it so True/False can't silently map to 1/0.
        if isinstance(toggl_project_id, bool):
            raise ValueError("toggl_project_id must be an integer, not a boolean")
        try:
            profile["toggl_project_id"] = int(toggl_project_id)
        except (TypeError, ValueError):
            raise ValueError("toggl_project_id must be an integer (Toggl numeric project id)")
    return profile


def default_worklog_path(script_dir: Path) -> Path:
    """Default timelog file in the project: TIMELOG.md."""
    cwd = Path.cwd() / "TIMELOG.md"
    if cwd.is_file():
        return cwd
    local = script_dir / "TIMELOG.md"
    if local.is_file():
        return local
    return script_dir / "TIMELOG.md"


def resolve_worklog_path(cli_worklog, config_path, workspace_worklog, script_dir: Path):
    if cli_worklog is not None:
        return Path(cli_worklog).expanduser()
    if workspace_worklog:
        p = Path(str(workspace_worklog).strip()).expanduser()
        if not p.is_absolute():
            base = Path(config_path).parent if config_path else script_dir
            p = (base / p).resolve()
        return p
    return default_worklog_path(script_dir)


def resolve_profile_worklog_paths(
    profiles,
    *,
    config_path: Optional[Path],
    script_dir: Path,
) -> list[Path]:
    """Resolve optional per-project worklog paths from normalized profiles."""
    out: list[Path] = []
    seen: set[Path] = set()
    base = Path(config_path).parent if config_path else script_dir
    for profile in profiles or []:
        raw = str((profile or {}).get("worklog", "")).strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (base / path).resolve()
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def load_profiles(config_path, args):
    cfg = Path(config_path)
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            workspace = {}
            if isinstance(data, dict):
                raw_profiles = data.get("projects", [])
                wl = data.get("worklog")
                if wl is not None and str(wl).strip():
                    workspace["worklog"] = str(wl).strip()
            elif isinstance(data, list):
                raw_profiles = data
            else:
                raise ValueError("JSON must be an object or a list")
            profiles = []
            for raw_profile in raw_profiles:
                if not isinstance(raw_profile, dict):
                    raise ValueError("Each project profile must be a JSON object")
                if not bool(raw_profile.get("enabled", True)):
                    continue
                profiles.append(normalize_profile(raw_profile))
            if profiles:
                return profiles, cfg, workspace
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"[Warning] Could not read project config {cfg}: {exc}")

    fallback = normalize_profile(
        {
            "name": args.project,
            "match_terms": as_list(args.keywords) + [args.project],
            "email": args.email,
        }
    )
    return [fallback], None, {}


def load_projects_config_payload(config_path: Path) -> dict:
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            data = {"projects": data}
        if not isinstance(data, dict):
            raise ValueError("projects config must be an object or list")
        data.setdefault("projects", [])
        return data
    return {"projects": [], "worklog": "TIMELOG.md"}


def backup_projects_config_if_exists(config_path: Path) -> Optional[Path]:
    """Copy existing config to a timestamped sibling file; no-op if missing."""
    if not config_path.is_file():
        return None
    ts = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    backup_path = config_path.parent / f"{config_path.stem}.backup.{ts}{config_path.suffix}"
    shutil.copy2(config_path, backup_path)
    return backup_path


def _preserve_non_normalized_fields(normalized: dict, target: dict, fallback_name: str) -> None:
    """Copy runtime-editable fields from target into normalized profile dict."""
    normalized["enabled"] = bool(target.get("enabled", True))
    normalized["project_id"] = str(target.get("project_id", "")).strip() or fallback_name
    normalized["ticket_mode"] = str(target.get("ticket_mode", "")).strip().lower() or "optional"
    if normalized["ticket_mode"] not in {"required", "optional", "none"}:
        normalized["ticket_mode"] = "optional"
    normalized["default_client"] = str(target.get("default_client", "")).strip() or str(
        target.get("customer", "")
    ).strip() or fallback_name
    normalized["email"] = str(target.get("email", "")).strip()
    normalized["invoice_title"] = str(target.get("invoice_title", "")).strip()
    normalized["invoice_description"] = str(target.get("invoice_description", "")).strip()
    normalized["customer"] = str(target.get("customer", "")).strip() or fallback_name


def save_projects_config_payload(config_path: Path, payload: dict) -> None:
    parent_dir = config_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file in the same directory for atomic replacement
    fd, temp_path = tempfile.mkstemp(dir=parent_dir, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json.dumps(payload, indent=2, ensure_ascii=False))
            f.flush()
            os.fsync(f.fileno())

        # Fsync the parent directory to ensure the file is durably written
        dir_fd = os.open(parent_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

        # Atomically replace the target file
        os.replace(temp_path, config_path)
    except:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def apply_rule_to_project(
    payload: dict,
    *,
    project_name: str,
    rule_type: str,
    rule_value: str,
    customer: str | None = None,
    invoice_title: str | None = None,
) -> tuple[str, str, bool]:
    cleaned_name = str(project_name).strip()
    if not cleaned_name:
        raise ValueError("project_name is required")
    cleaned_value = str(rule_value).strip()
    if not cleaned_value:
        raise ValueError("rule_value is required")
    if rule_type not in {"match_terms", "tracked_urls"}:
        raise ValueError(f"unsupported rule_type: {rule_type}")

    projects = payload.setdefault("projects", [])
    if not isinstance(projects, list):
        raise ValueError("payload.projects must be a list")

    target: dict | None = None
    for project in projects:
        if not isinstance(project, dict):
            continue
        if str(project.get("name", "")).strip().lower() == cleaned_name.lower():
            target = project
            break

    created = False
    if target is None:
        created = True
        cleaned_customer = str(customer or "").strip() or cleaned_name
        cleaned_title = str(invoice_title or "").strip()
        alias_values = [cleaned_name]
        if cleaned_title and cleaned_title.lower() != cleaned_name.lower():
            alias_values.append(cleaned_title)
        target = {
            "name": cleaned_name,
            "project_id": cleaned_name,
            "customer": cleaned_customer,
            "ticket_mode": "optional",
            "default_client": cleaned_customer,
            "match_terms": [cleaned_name],
            "tracked_urls": [],
            "canonical_project": cleaned_name,
            "aliases": alias_values,
            "email": "",
            "invoice_title": cleaned_title,
            "invoice_description": "",
            "enabled": True,
        }
        projects.append(target)

    values = as_list(target.get(rule_type))
    values.append(cleaned_value)
    target[rule_type] = sorted({value for value in values if value})

    normalized = normalize_profile(target)
    _preserve_non_normalized_fields(normalized, target, cleaned_name)
    target.clear()
    target.update(normalized)
    return rule_type, cleaned_value, created


def remove_rule_from_project(
    payload: dict,
    *,
    project_name: str,
    rule_type: str,
    rule_value: str,
) -> bool:
    """Remove one match_terms or tracked_urls value from a project. Returns True if a row was removed."""
    cleaned_name = str(project_name).strip()
    cleaned_val = str(rule_value).strip()
    if not cleaned_name or not cleaned_val:
        raise ValueError("project_name and rule_value are required")
    if rule_type not in {"match_terms", "tracked_urls"}:
        raise ValueError(f"unsupported rule_type: {rule_type}")

    projects = payload.get("projects", [])
    if not isinstance(projects, list):
        raise ValueError("payload.projects must be a list")

    for target in projects:
        if not isinstance(target, dict):
            continue
        if str(target.get("name", "")).strip().lower() != cleaned_name.lower():
            continue
        key = rule_type
        raw_list = as_list(target.get(key))
        if not raw_list:
            return False
        kept = [v for v in raw_list if str(v).strip().lower() != cleaned_val.lower()]
        if len(kept) == len(raw_list):
            return False
        # Keep project shape as-is after removals; normalizing here would
        # re-introduce fallback match_terms like the project name.
        compact: list[str] = []
        seen: set[str] = set()
        for value in kept:
            sval = str(value).strip()
            if not sval:
                continue
            marker = sval.lower()
            if marker in seen:
                continue
            seen.add(marker)
            compact.append(sval)
        target[key] = compact
        return True
    return False