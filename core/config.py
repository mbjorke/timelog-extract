"""Configuration/profile normalization utilities."""

from __future__ import annotations

import json
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
            profiles = [normalize_profile(p) for p in raw_profiles if bool(p.get("enabled", True))]
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
