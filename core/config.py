"""Configuration/profile normalization utilities."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


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
    match_terms_input = as_list(raw.get("match_terms")) or [name]
    tracked_urls = as_list(raw.get("tracked_urls"))
    email = str(raw.get("email", "")).strip()
    customer = str(raw.get("customer", "")).strip() or name
    invoice_title = str(raw.get("invoice_title", "")).strip()
    invoice_description = str(raw.get("invoice_description", "")).strip()
    enabled = bool(raw.get("enabled", True))
    terms = sorted(
        {
            t.lower()
            for t in (match_terms_input + [name])
            if t
        }
    )
    merged_tracked_urls = sorted({url for url in tracked_urls if url})
    return {
        "name": name,
        "enabled": enabled,
        "match_terms": terms,
        "tracked_urls": merged_tracked_urls,
        "email": email,
        "customer": customer,
        "invoice_title": invoice_title,
        "invoice_description": invoice_description,
    }


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
        target = {
            "name": cleaned_name,
            "customer": cleaned_name,
            "match_terms": [cleaned_name],
            "tracked_urls": [],
            "email": "",
            "invoice_title": "",
            "invoice_description": "",
            "enabled": True,
        }
        projects.append(target)

    values = as_list(target.get(rule_type))
    values.append(cleaned_value)
    target[rule_type] = sorted({value for value in values if value})

    normalized = normalize_profile(target)
    normalized["enabled"] = bool(target.get("enabled", True))
    normalized["email"] = str(target.get("email", "")).strip()
    normalized["invoice_title"] = str(target.get("invoice_title", "")).strip()
    normalized["invoice_description"] = str(target.get("invoice_description", "")).strip()
    normalized["customer"] = str(target.get("customer", "")).strip() or cleaned_name
    target.clear()
    target.update(normalized)
    return rule_type, cleaned_value, created