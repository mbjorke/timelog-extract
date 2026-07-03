#!/usr/bin/env python3
"""GitHub Projects board helpers for the kanin-loop (issues + pull requests)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


class BoardError(Exception):
    """Board API or configuration failure."""


def _run_gh(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise BoardError(f"gh command timed out: {' '.join(args)}") from exc


def _load_json(proc: subprocess.CompletedProcess[str], context: str) -> Any:
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise BoardError(f"invalid JSON from {context}: {exc}") from exc


_OWNER_KIND_CACHE: dict[str, str] = {}


def owner_kind(owner: str) -> str:
    if owner in _OWNER_KIND_CACHE:
        return _OWNER_KIND_CACHE[owner]
    if _run_gh(["gh", "api", f"users/{owner}"]).returncode == 0:
        kind = "user"
    elif _run_gh(["gh", "api", f"orgs/{owner}"]).returncode == 0:
        kind = "organization"
    else:
        raise BoardError(f"owner {owner!r} not found as user or organization")
    _OWNER_KIND_CACHE[owner] = kind
    return kind


def _graphql(login: str, project_number: int, query: str, **variables: Any) -> dict:
    args = ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"login={login}", "-F", f"number={project_number}"]
    for key, value in variables.items():
        if value is not None:
            args.extend(["-f", f"{key}={value}"])
    proc = _run_gh(args)
    if proc.returncode != 0:
        raise BoardError((proc.stderr or proc.stdout or "gh api graphql failed").strip())
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise BoardError(f"invalid GraphQL JSON: {exc}") from exc
    for err in data.get("errors") or []:
        raise BoardError(err.get("message") or str(err))
    return data


def project_node_id(owner: str, project_number: int) -> str:
    proc = _run_gh(["gh", "project", "view", str(project_number), "--owner", owner, "--format", "json"])
    if proc.returncode != 0:
        raise BoardError(f"could not read project {project_number} (owner {owner})")
    return _load_json(proc, "gh project view")["id"]


def status_field_option(owner: str, project_number: int, status_name: str) -> tuple[str, str]:
    proc = _run_gh(["gh", "project", "field-list", str(project_number), "--owner", owner, "--format", "json"])
    if proc.returncode != 0:
        raise BoardError(f"could not list fields for project {project_number}")
    for field in _load_json(proc, "gh project field-list").get("fields", []):
        if field.get("name") == "Status":
            for option in field.get("options", []):
                if option.get("name") == status_name:
                    return field["id"], option["id"]
            raise BoardError(f"status column {status_name!r} not found on the board")
    raise BoardError("no Status field on the board")


def find_item_by_url(owner: str, project_number: int, content_url: str) -> str | None:
    root = "user" if owner_kind(owner) == "user" else "organization"
    query = f"""
query($login: String!, $number: Int!, $after: String) {{
  {root}(login: $login) {{
    projectV2(number: $number) {{
      items(first: 100, after: $after) {{
        pageInfo {{ hasNextPage endCursor }}
        nodes {{
          id
          content {{
            ... on Issue {{ url }}
            ... on PullRequest {{ url }}
          }}
        }}
      }}
    }}
  }}
}}
"""
    after: str | None = None
    while True:
        data = _graphql(login=owner, project_number=project_number, query=query, after=after)
        owner_node = (data.get("data") or {}).get(root)
        if owner_node is None:
            raise BoardError(f"owner {owner!r} not found or not accessible")
        project = owner_node.get("projectV2")
        if project is None:
            raise BoardError(f"project #{project_number} not found for {owner!r}")
        block = project["items"]
        for node in block["nodes"]:
            url = (node.get("content") or {}).get("url")
            if url == content_url:
                return node["id"]
        if not block["pageInfo"]["hasNextPage"]:
            return None
        after = block["pageInfo"]["endCursor"]


def add_item(owner: str, project_number: int, content_url: str) -> str:
    proc = _run_gh(
        ["gh", "project", "item-add", str(project_number), "--owner", owner, "--url", content_url, "--format", "json"]
    )
    if proc.returncode != 0:
        raise BoardError(f"could not add {content_url} to the board")
    return _load_json(proc, "gh project item-add")["id"]


def set_item_status(project_id: str, item_id: str, field_id: str, option_id: str) -> None:
    proc = _run_gh(
        [
            "gh",
            "project",
            "item-edit",
            "--id",
            item_id,
            "--project-id",
            project_id,
            "--field-id",
            field_id,
            "--single-select-option-id",
            option_id,
        ]
    )
    if proc.returncode != 0:
        raise BoardError(f"could not set Status on board item {item_id}")


def sync_content_url(
    *,
    owner: str,
    project_number: int,
    content_url: str,
    status_name: str,
    dry_run: bool = False,
) -> str:
    """Add or update a board item. Returns item id (or would-add sentinel on dry-run)."""
    field_id, option_id = status_field_option(owner, project_number, status_name)
    item_id = find_item_by_url(owner, project_number, content_url)
    if dry_run:
        action = "update" if item_id else "add"
        return f"dry-run:{action}:{content_url}"
    project_id = project_node_id(owner, project_number)
    if not item_id:
        item_id = add_item(owner, project_number, content_url)
    set_item_status(project_id, item_id, field_id, option_id)
    return item_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync a GitHub issue or PR URL to a project board Status.")
    parser.add_argument("--owner", default="mbjorke")
    parser.add_argument("--project", type=int, default=3)
    parser.add_argument("--url", required=True, help="Issue or pull request URL")
    parser.add_argument("--status", required=True, help="Status column name (e.g. 'In review')")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        item_id = sync_content_url(
            owner=args.owner,
            project_number=args.project,
            content_url=args.url,
            status_name=args.status,
            dry_run=args.dry_run,
        )
    except BoardError as exc:
        print(f"rabbit_board: {exc}", file=sys.stderr)
        sys.exit(2)
    print(item_id)


if __name__ == "__main__":
    main()
