#!/usr/bin/env python3
"""Generate the Claude Code plugin's test fixture from a mock Gittan home.

Nothing in the fixture is hand-written. The script builds a throwaway HOME,
installs the real global post-commit hook (``core.global_timelog_hook_script``)
into neutral fixture repos, commits there so the hook writes the central
``~/.gittan/worklogs/<project>.md`` files exactly as it does on a real
machine, then runs ``report --today --format json`` against that home. The
truth payload it prints (temp root shown as ``/mock``) and the
``statusline --cwd`` line for each fixture repo become
``claude-code-plugin/tests/fixture.ts``.

Usage (repo root):
    python3 scripts/build_claude_plugin_fixture.py           # write the fixture
    python3 scripts/build_claude_plugin_fixture.py --check   # exit 1 if it would change

Needs ``zsh`` (the hook's interpreter) and ``git``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.global_timelog_hook_script import HOOK_BODY  # noqa: E402

FIXTURE_PATH = REPO_ROOT / "claude-code-plugin" / "tests" / "fixture.ts"
MOCK_ROOT = "/mock"

# Neutral placeholders only (AGENTS.md: test and fixture data hygiene).
PROJECTS = {"project-alpha": 3, "project-beta": 1}
UNMATCHED_REPO = "scratch-notes"

# Fields that change on every run without saying anything about behaviour.
VOLATILE_KEYS = ("generator", "range")


def _git(repo: Path, *args: str, env: dict[str, str]) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def build_home(root: Path) -> dict[str, str]:
    home = root / "home"
    data = home / ".gittan"
    hooks = root / "hooks"
    for path in (data, hooks, home / "code"):
        path.mkdir(parents=True, exist_ok=True)

    config = {
        "projects": [
            {
                "name": name,
                "project_id": name,
                "match_terms": [name],
                # What `gittan setup` bootstraps: an explicit central worklog.
                "worklog": f"worklogs/{name}.md",
            }
            for name in PROJECTS
        ]
    }
    config_path = data / "timelog_projects.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    hook = hooks / "post-commit"
    hook.write_text(HOOK_BODY, encoding="utf-8")
    hook.chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home),
        "GITTAN_HOME": str(data),
        # The hook ignores repos under temp dirs unless told this is deliberate.
        "GITTAN_HOOK_ALLOW_TEMP": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    for name, commits in {**PROJECTS, UNMATCHED_REPO: 1}.items():
        repo = home / "code" / name
        repo.mkdir()
        _git(repo, "init", "-q", env=env)
        _git(repo, "config", "user.name", "Fixture User", env=env)
        _git(repo, "config", "user.email", "fixture@example.test", env=env)
        _git(repo, "config", "core.hooksPath", str(hooks), env=env)
        # The statusline resolves the project from the remote's owner/repo slug.
        _git(repo, "remote", "add", "origin", f"https://github.com/example-owner/{name}.git", env=env)
        for i in range(1, commits + 1):
            _git(repo, "commit", "-q", "--allow-empty", "-m", f"{name} change {i}", env=env)
    return env


def _gittan(env: dict[str, str], cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "timelog_extract.py"), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def run_report(env: dict[str, str], cwd: Path) -> dict:
    out = _gittan(env, cwd, "report", "--today", "--format", "json", "--screen-time", "off", "--quiet")
    return json.loads(out[out.index("{"):])


def run_statuslines(env: dict[str, str], root: Path) -> dict[str, str]:
    """`gittan statusline --cwd <repo>` per fixture repo, after the report ran."""
    code = root / "home" / "code"
    return {
        name: _gittan(env, root, "statusline", "--cwd", str(code / name)).strip()
        for name in (*PROJECTS, UNMATCHED_REPO)
    }


def render(payload: dict, statuslines: dict[str, str], root: Path) -> str:
    for key in VOLATILE_KEYS:
        payload.pop(key, None)
    # Mask the temp root first, then the clock: commit times are wall time, so
    # every timestamp the hook wrote is "now". The plugin reads hours, not times.
    text = json.dumps(payload, indent=2, sort_keys=True).replace(str(root), MOCK_ROOT)
    payload = json.loads(text)
    for day in list(payload.get("days", {})):
        payload["days"]["2000-01-01"] = payload["days"].pop(day)
    _mask_times(payload)
    body = json.dumps(payload, indent=2, sort_keys=True)
    return (
        "// Generated by scripts/build_claude_plugin_fixture.py; do not edit by hand.\n"
        "// A real `gittan report --today --format json` over central worklogs the\n"
        "// post-commit hook wrote in a mock home (temp root shown as /mock, clock\n"
        "// masked to 2000-01-01T00:00:00Z).\n\n"
        f"export const MOCK_ROOT = {json.dumps(MOCK_ROOT)}\n"
        f"export const UNMATCHED_REPO = {json.dumps(UNMATCHED_REPO)}\n\n"
        f"export const STATUSLINES: Record<string, string> = {json.dumps(statuslines, indent=2, ensure_ascii=False)}\n\n"
        f"export const TODAY_PAYLOAD = {body}\n"
    )


def _mask_times(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"start", "end", "start_local", "end_local", "timestamp", "local_time"} and isinstance(value, str):
                node[key] = "2000-01-01T00:00:00+00:00"
            elif key in {"id", "day"} and isinstance(value, str) and value[:4].isdigit():
                node[key] = value.replace(value[:10], "2000-01-01")
            else:
                _mask_times(value)
    elif isinstance(node, list):
        for item in node:
            _mask_times(item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the fixture is stale")
    args = parser.parse_args()
    if not shutil.which("zsh"):
        print("build_claude_plugin_fixture: zsh not found (the hook runs under zsh)", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="gittan-plugin-fixture-") as tmp:
        root = Path(tmp).resolve()
        env = build_home(root)
        # A plain terminal report first, as a person runs it: only that path
        # refreshes the observed cache the statusline reads (JSON runs skip it
        # by design, core/report_cli.py). Its output is not part of the fixture.
        _gittan(env, root, "report", "--today", "--screen-time", "off")
        payload = run_report(env, cwd=root)
        statuslines = run_statuslines(env, root)
        rendered = render(payload, statuslines, root)

    if args.check:
        current = FIXTURE_PATH.read_text(encoding="utf-8") if FIXTURE_PATH.exists() else ""
        if current != rendered:
            print(f"{FIXTURE_PATH.relative_to(REPO_ROOT)} is stale; rerun without --check", file=sys.stderr)
            return 1
        return 0
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {FIXTURE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
