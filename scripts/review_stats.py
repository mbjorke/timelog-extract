#!/usr/bin/env python3
"""Review stats for Gittan — a solo-repo take on Cloudflare's "show me the numbers".

Two data sources, both optional and privacy-preserving (local-first):

  1. Local ledger (.reviews/metrics.jsonl, git-ignored): one JSON line per review,
     appended by `/gittan-review` (and the kanin loop) via `record`. This is the
     only way to get severity/lens/tier breakdowns, since agent reviews are
     otherwise ephemeral.

  2. GitHub, retroactively (`github` subcommand): needs no instrumentation — reads
     merged PRs via `gh` to compute review throughput, cycles, and time-to-merge.

Cost/token percentiles (Cloudflare's headline numbers) are intentionally NOT
tracked: we do not run the models' billing infra, so any figure would be a guess.

Usage:
  scripts/review_stats.py record --reviewer gittan-review --verdict APPROVE \
      --tier full --critical 0 --high 1 --medium 2 --low 3
  scripts/review_stats.py show                 # aggregate the local ledger
  scripts/review_stats.py github --limit 100   # retroactive GitHub PR stats
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

LEDGER = Path(".reviews/metrics.jsonl")
SEVERITIES = ("critical", "high", "medium", "low")


def _run(cmd: list[str]) -> str:
    """Run a command, returning stdout; raise a friendly error on failure."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit(f"error: `{cmd[0]}` not found on PATH")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"error: `{' '.join(cmd)}` failed:\n{exc.stderr.strip()}")
    return out.stdout


def _git_branch() -> str:
    try:
        return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    except SystemExit:
        return "unknown"


def _repo_slug() -> str:
    return _run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()


# Review bots tag each inline finding with category chips like
# `<code>🐞 Bug</code>` / `<code>≡ Correctness</code>`, and a severity badge
# (`alt="Action required"` etc.). Bucket both for a Cloudflare-style breakdown.
# Category order = priority (first match wins when a finding has several chips).
_CATEGORY_WORDS = (
    "security",
    "bug",
    "correctness",
    "reliability",
    "performance",
    "potential issue",
    "possible issue",
    "maintainability",
    "refactor",
    "nitpick",
    "typo",
    "documentation",
)
_SEVERITY_BADGES = (
    ("action-required", "action required"),
    ("review-recommended", "review recommended"),
    ("remediation-recommended", "remediation recommended"),
)


def _categorise(body: str) -> str:
    low = body.lower()
    for word in _CATEGORY_WORDS:
        # Match the chip form (`bug</code>`) to avoid prose false positives.
        if f"{word}</code>" in low or f"{word} </code>" in low:
            return word.replace(" ", "-")
    return "uncategorised"


def _severity(body: str) -> str:
    low = body.lower()
    for name, needle in _SEVERITY_BADGES:
        if needle in low:
            return name
    return "unmarked"


# ---------------------------------------------------------------- record


def cmd_record(args: argparse.Namespace) -> int:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reviewer": args.reviewer,
        "verdict": args.verdict,
        "tier": args.tier,
        "branch": args.branch or _git_branch(),
        "pr": args.pr,
        "findings": {s: getattr(args, s) for s in SEVERITIES},
        "files": args.files,
        "lines": args.lines,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    total = sum(row["findings"].values())
    print(f"recorded: {args.reviewer} {args.verdict} tier={args.tier} findings={total} → {LEDGER}")
    return 0


# ------------------------------------------------------------------ show


def _load_ledger() -> list[dict]:
    if not LEDGER.exists():
        sys.exit(f"no ledger yet at {LEDGER} — run `record` first (or `/gittan-review`)")
    rows = []
    for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"warning: skipping malformed ledger line {i}", file=sys.stderr)
    return rows


def _counter(rows: list[dict], key) -> dict:
    out: dict = {}
    for r in rows:
        k = key(r)
        out[k] = out.get(k, 0) + 1
    return out


def _bar(n: int, total: int, width: int = 24) -> str:
    filled = 0 if total == 0 else round(width * n / total)
    return "█" * filled + "·" * (width - filled)


def _table(title: str, counts: dict, total: int) -> None:
    print(f"\n{title}")
    if not counts:
        print("  (none)")
        return
    for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        pct = 0 if total == 0 else 100 * n / total
        print(f"  {str(k):<22} {n:>4}  {pct:5.1f}%  {_bar(n, total)}")


def cmd_show(args: argparse.Namespace) -> int:
    rows = _load_ledger()
    total = len(rows)
    print(f"Gittan review ledger — {total} reviews ({LEDGER})")

    sev_totals = {s: 0 for s in SEVERITIES}
    for i, r in enumerate(rows, 1):
        f = r.get("findings")
        if not isinstance(f, dict):
            print(f"warning: skipping row {i} with invalid findings", file=sys.stderr)
            continue
        for s in SEVERITIES:
            try:
                sev_totals[s] += int(f.get(s, 0) or 0)
            except (TypeError, ValueError):
                print(f"warning: row {i} has non-numeric {s} finding", file=sys.stderr)
    findings = sum(sev_totals.values())
    per_review = findings / total if total else 0
    print(f"findings: {findings} total, {per_review:.2f} per review")

    _table("By reviewer", _counter(rows, lambda r: r.get("reviewer", "?")), total)
    _table("By verdict", _counter(rows, lambda r: r.get("verdict", "?")), total)
    _table("By risk tier", _counter(rows, lambda r: r.get("tier", "?")), total)
    _table("Findings by severity", sev_totals, findings)

    blocking = sum(1 for r in rows if r.get("verdict") == "CHANGES_REQUESTED")
    approve_rate = 100 * (total - blocking) / total if total else 0
    print(
        f"\napprove-rate (not CHANGES_REQUESTED): {approve_rate:.1f}%  ({total - blocking}/{total})"
    )
    return 0


# ---------------------------------------------------------------- github


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Nearest-rank percentile (q in [0,1]); sorted_vals must be ascending."""
    if not sorted_vals:
        return 0.0
    idx = max(0, math.ceil(q * len(sorted_vals)) - 1)
    return sorted_vals[idx]


def cmd_github(args: argparse.Namespace) -> int:
    fields = "number,title,author,createdAt,mergedAt,reviews,comments"
    raw = _run(
        ["gh", "pr", "list", "--state", "merged", "--limit", str(args.limit), "--json", fields]
    )
    prs = json.loads(raw)
    if not prs:
        print("no merged PRs found")
        return 0

    hours: list[float] = []
    bot_reviews = 0
    human_reviews = 0
    bot_names = {"coderabbitai", "coderabbitai[bot]", "qodo-merge-pro", "github-actions[bot]"}
    for pr in prs:
        created, merged = pr.get("createdAt"), pr.get("mergedAt")
        if created and merged:
            hours.append((_parse_iso(merged) - _parse_iso(created)).total_seconds() / 3600)
        for rv in pr.get("reviews", []) or []:
            login = (rv.get("author") or {}).get("login", "").lower()
            if login in bot_names or "bot" in login:
                bot_reviews += 1
            else:
                human_reviews += 1

    n = len(prs)
    print(f"GitHub — {n} merged PRs (last {args.limit} scanned)")
    if hours:
        hours.sort()
        p90 = _percentile(hours, 0.9)
        print(
            f"time-to-merge: median {median(hours):.1f}h, "
            f"p90 {p90:.1f}h, fastest {hours[0]:.1f}h, slowest {hours[-1]:.1f}h"
        )
    print(
        f"review submissions: {bot_reviews} bot, {human_reviews} human "
        f"({(bot_reviews + human_reviews) / n:.2f} per PR)"
    )

    authors = _counter(prs, lambda p: (p.get("author") or {}).get("login", "?"))
    _table("Merged PRs by author", authors, n)

    if args.deep:
        _deep_findings(prs)
    else:
        print(
            "\nnote: per-finding severity needs the local ledger (`show`), or pass "
            "`--deep` to count review-bot findings from PR history (1 API call/PR)."
        )
    return 0


def _pr_inline_findings(slug: str, number: int) -> list[dict]:
    """Inline review comments for one PR (first 100; enough for a solo repo).

    Resilient by design: a failure on one PR (deleted, permissions, API hiccup)
    warns and returns [] so a `--deep` scan continues instead of aborting.
    """
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{slug}/pulls/{number}/comments?per_page=100"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(out.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        print(f"warning: could not scan PR #{number}: {detail.strip()[:120]}", file=sys.stderr)
        return []


def _deep_findings(prs: list[dict]) -> None:
    """Count review-bot inline findings across PRs, bucketed by CodeRabbit marker."""
    slug = _repo_slug()
    by_category: dict = {}
    by_severity: dict = {}
    by_bot: dict = {}
    prs_with_findings = 0
    total = 0
    for i, pr in enumerate(prs, 1):
        number = pr.get("number")
        print(f"  scanning PR #{number} ({i}/{len(prs)})…", end="\r", file=sys.stderr)
        comments = _pr_inline_findings(slug, number)
        found_here = 0
        for c in comments:
            login = (c.get("user") or {}).get("login", "").lower()
            if "bot" not in login and login not in {"coderabbitai", "qodo-merge-pro"}:
                continue
            body = c.get("body", "")
            found_here += 1
            total += 1
            by_bot[login] = by_bot.get(login, 0) + 1
            cat = _categorise(body)
            by_category[cat] = by_category.get(cat, 0) + 1
            sev = _severity(body)
            by_severity[sev] = by_severity.get(sev, 0) + 1
        if found_here:
            prs_with_findings += 1
    print(" " * 48, end="\r", file=sys.stderr)  # clear progress line

    n = len(prs)
    per_pr = total / n if n else 0
    print(
        f"\nreview-bot inline findings (deep): {total} across {prs_with_findings}/"
        f"{n} PRs, {per_pr:.2f} per PR"
    )
    _table("Findings by severity (badge)", by_severity, total)
    _table("Findings by category (chip)", by_category, total)
    _table("Findings by bot", by_bot, total)


# ------------------------------------------------------------------ main


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="append one review to the local ledger")
    rec.add_argument(
        "--reviewer", required=True, help="gittan-review | coderabbit | code-review-ultra | ..."
    )
    rec.add_argument(
        "--verdict", required=True, help="APPROVE | APPROVE_WITH_COMMENTS | CHANGES_REQUESTED"
    )
    rec.add_argument("--tier", default="full", help="docs | lite | full")
    rec.add_argument("--branch", default=None)
    rec.add_argument("--pr", default=None)
    rec.add_argument("--files", type=int, default=None)
    rec.add_argument("--lines", type=int, default=None)
    for s in SEVERITIES:
        rec.add_argument(f"--{s}", type=int, default=0)
    rec.set_defaults(func=cmd_record)

    sh = sub.add_parser("show", help="aggregate the local ledger")
    sh.set_defaults(func=cmd_show)

    gh = sub.add_parser("github", help="retroactive PR stats via `gh` (no instrumentation)")
    gh.add_argument("--limit", type=int, default=100)
    gh.add_argument(
        "--deep",
        action="store_true",
        help="also count review-bot inline findings per PR (1 API call/PR)",
    )
    gh.set_defaults(func=cmd_github)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
