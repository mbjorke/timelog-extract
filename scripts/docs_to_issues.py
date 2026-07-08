#!/usr/bin/env python3
"""Turn planning docs into GitHub issues — idempotently.

Each ``docs/task-prompts/*.md`` spec becomes one issue: its ``# Title`` is the
issue title, its ``## Traceability`` (story_id / spec_status / implementation_status)
and its ```gherkin``` Behavior Contract become the body (acceptance criteria). Specs
whose implementation is already done are skipped (unless ``--include-done``).

Idempotent: every generated issue carries a hidden marker
``<!-- docs2issue: <path> -->``; a re-run skips any spec that already has one, so it
is safe to run repeatedly as new specs land. Dry-run by default.

See docs/skills/docs-to-issues.md.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKER = "docs2issue"
TASK_PROMPTS = REPO_ROOT / "docs" / "task-prompts"

# implementation_status values that mean "already built" → skip by default.
_DONE_WORDS = ("shipped", "done", "implemented", "complete", "landed", "merged", "closed",
               "built", "released", "verified")

# task-prompt files that are meta, not actionable tasks → never ticket.
_SKIP_STEMS = {"implementation-status", "task-traceability-template"}


def _field(block: str, key: str) -> str:
    """Read ``- key: value`` from a Traceability block.

    Captures the whole value line and strips backticks, so inline-code wrapping
    anywhere in the value (e.g. ``implementation_status: `now` items shipped``)
    does not truncate it — an earlier ``[^`]+`` stopped at the first backtick and
    lost the "shipped" that marks the spec as done.
    """
    m = re.search(rf"^\s*-?\s*{re.escape(key)}\s*:\s*(.+?)\s*$", block, re.M)
    return m.group(1).replace("`", "").strip() if m else ""


def _gherkin_blocks(text: str) -> List[str]:
    return [g.strip() for g in re.findall(r"```gherkin\n(.*?)```", text, re.S)]


def parse_task_prompt(text: str, stem: str = "") -> Dict[str, Any]:
    """Extract title, traceability fields, and gherkin from a task-prompt's markdown."""
    title_m = re.search(r"^#\s+(.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else stem
    trace_m = re.search(r"##\s*Traceability(.*?)(?:\n##\s|\Z)", text, re.S)
    trace = trace_m.group(1) if trace_m else ""
    story_raw = _field(trace, "story_id")
    story_m = re.search(r"GH-[\w]+", story_raw)  # keep just the id token, drop trailing prose
    return {
        "title": title,
        "story_id": story_m.group(0) if story_m else "",
        "spec_status": _field(trace, "spec_status"),
        "impl_status": _field(trace, "implementation_status"),
        "gherkin": _gherkin_blocks(text),
    }


def is_done(impl_status: str) -> bool:
    s = impl_status.lower()
    if "not " in s:  # "not built", "not done", "not started" → NOT done
        return False
    return any(re.search(rf"\b{w}\b", s) for w in _DONE_WORDS)


def build_body(item: Dict[str, Any], rel_path: str) -> str:
    lines = [
        f"**Source spec:** `{rel_path}`",
        f"**Story:** {item['story_id'] or '—'} · spec: {item['spec_status'] or '?'} "
        f"· impl: {item['impl_status'] or '?'}",
        "",
    ]
    if item["gherkin"]:
        lines.append("## Acceptance criteria")
        for g in item["gherkin"]:
            lines.append("```gherkin\n" + g + "\n```")
        lines.append("")
    lines.append(f"<!-- {MARKER}: {rel_path} -->")
    return "\n".join(lines)


def _existing_marked_paths() -> set:
    """Doc paths that already have an issue (found via the hidden marker)."""
    out = subprocess.run(
        ["gh", "issue", "list", "--state", "all", "--limit", "500",
         "--search", MARKER, "--json", "body"],
        capture_output=True, text=True,
    )
    paths: set = set()
    if out.returncode == 0 and out.stdout.strip():
        for issue in json.loads(out.stdout):
            paths.update(re.findall(rf"<!-- {MARKER}: (.+?) -->", issue.get("body", "")))
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate GitHub issues from planning docs.")
    ap.add_argument("--apply", action="store_true", help="create issues (default: dry-run)")
    ap.add_argument("--include-done", action="store_true", help="also include already-built specs")
    ap.add_argument("--project", help="project number to add created issues to (needs project scope)")
    ap.add_argument("--owner", default="mbjorke", help="project owner (with --project)")
    args = ap.parse_args()

    prompts = [p for p in sorted(TASK_PROMPTS.glob("*.md")) if p.stem not in _SKIP_STEMS]
    items = []
    for p in prompts:
        it = parse_task_prompt(p.read_text(encoding="utf-8"), p.stem)
        it["rel"] = str(p.relative_to(REPO_ROOT))
        items.append(it)
    if not args.include_done:
        items = [it for it in items if not is_done(it["impl_status"])]

    have = _existing_marked_paths()
    todo = [it for it in items if it["rel"] not in have]

    print(f"task-prompts: {len(prompts)} | candidates: {len(items)} | "
          f"already ticketed: {len(items) - len(todo)} | to create: {len(todo)}\n")
    for it in todo:
        tag = f" [{it['story_id']}]" if it["story_id"] else ""
        print(f"  + {it['title']}{tag}  ({it['rel']}, {len(it['gherkin'])} gherkin)")

    if not args.apply:
        print("\n(dry-run — pass --apply to create these issues)")
        return 0

    for it in todo:
        title = it["title"] + (f" [{it['story_id']}]" if it["story_id"] else "")
        r = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", build_body(it, it["rel"])],
            capture_output=True, text=True,
        )
        url = r.stdout.strip()
        print(f"created {url}" if r.returncode == 0 else f"FAILED {it['title']}: {r.stderr.strip()}")
        if r.returncode == 0 and args.project and url:
            subprocess.run(
                ["gh", "project", "item-add", args.project, "--owner", args.owner, "--url", url],
                capture_output=True, text=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
