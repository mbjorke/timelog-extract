#!/usr/bin/env python3
"""Render .rabbit-loop/preflight.json as markdown for agent/human chat."""

from __future__ import annotations

import json
import sys


def render_chat_summary(data: dict) -> str:
    head = data.get("head") or ""
    short = head[:7] if head else "?"
    dirty = "yes" if data.get("dirty") else "no"
    lines = [
        "## Kanin-loop workflow preflight",
        "",
        f"**Branch:** `{data.get('branch', '')}` @ `{short}` · "
        f"**mode:** {data.get('workflow_mode', '?')} · **dirty:** {dirty}",
        "",
    ]

    def section(title: str, items: list, bullet_fmt) -> None:
        lines.append(f"### {title}")
        if not items:
            lines.append("- _(none)_")
        else:
            for item in items:
                lines.append(bullet_fmt(item))
        lines.append("")

    section(
        "Blockers",
        data.get("blockers") or [],
        lambda b: f"- **[{b.get('kind', '?')}]** {b.get('detail', '')}",
    )
    section(
        "Warnings",
        data.get("warnings") or [],
        lambda w: f"- **[{w.get('kind', '?')}]** {w.get('detail', '')}",
    )

    lines.append("### Questions")
    lines.append("_Answer in chat, then run the ack command below._")
    lines.append("")
    for i, q in enumerate(data.get("questions") or [], 1):
        qid = q.get("id", "?")
        prompt = q.get("prompt", "")
        lines.append(f"{i}. **{qid}** — {prompt}")
        for opt in q.get("options") or []:
            lines.append(f"   - {opt}")
        lines.append("")

    lanes = data.get("local_task_lanes") or []
    lines.append("### Local task/* lanes")
    if not lanes:
        lines.append("_(none)_")
    else:
        lines.append("| Branch | Date | Subject | Upstream | ± |")
        lines.append("| --- | --- | --- | --- | --- |")
        for lane in lanes[:12]:
            mark = " **← current**" if lane.get("current") else ""
            subj = (lane.get("subject") or "")[:60]
            lines.append(
                f"| `{lane.get('branch', '')}`{mark} | {(lane.get('date') or '')[:10]} | "
                f"{subj} | `{lane.get('upstream') or ''}` | "
                f"+{lane.get('ahead', '?')}/-{lane.get('behind', '?')} |"
            )
        if len(lanes) > 12:
            lines.append(f"| … | | _{len(lanes) - 12} more in preflight.html_ | | |")
    lines.append("")

    prs = data.get("open_prs") or []
    lines.append("### Open PRs")
    if not prs:
        lines.append("_(none / gh unavailable)_")
    else:
        for pr in prs[:10]:
            title = (pr.get("title") or "")[:80]
            num = pr.get("number", "?")
            url = pr.get("url", "")
            branch = pr.get("branch", "")
            lines.append(f"- [#{num}]({url}) `{branch}` — {title}")
    lines.append("")

    worktrees = data.get("worktrees") or []
    lines.append("### Worktrees")
    if not worktrees:
        lines.append("- Primary clone only")
    else:
        for path in worktrees:
            lines.append(f"- `{path}`")
    lines.append("")

    applied = data.get("but_applied") or []
    if applied:
        lines.append("### GitButler applied (excerpt)")
        for row in applied[:8]:
            lines.append(f"- `{row}`")
        lines.append("")

    ack = data.get("ack_command", "scripts/rabbit_workflow_context.sh --ack")
    lines.append(f"**Next:** `{ack}`")
    lines.append("")
    lines.append("_Full tables: `.rabbit-loop/preflight.html`_")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: rabbit_workflow_context_chat.py <preflight.json>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    print(render_chat_summary(data))


if __name__ == "__main__":
    main()
