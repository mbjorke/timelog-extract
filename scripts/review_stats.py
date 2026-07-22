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
    print(f"recorded: {args.reviewer} {args.verdict} tier={args.tier} "
          f"findings={total} → {LEDGER}")
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

    sev_totals = {s: sum(r.get("findings", {}).get(s, 0) for r in rows) for s in SEVERITIES}
    findings = sum(sev_totals.values())
    per_review = findings / total if total else 0
    print(f"findings: {findings} total, {per_review:.2f} per review")

    _table("By reviewer", _counter(rows, lambda r: r.get("reviewer", "?")), total)
    _table("By verdict", _counter(rows, lambda r: r.get("verdict", "?")), total)
    _table("By risk tier", _counter(rows, lambda r: r.get("tier", "?")), total)
    _table("Findings by severity", sev_totals, findings)

    blocking = sum(1 for r in rows if r.get("verdict") == "CHANGES_REQUESTED")
    approve_rate = 100 * (total - blocking) / total if total else 0
    print(f"\napprove-rate (not CHANGES_REQUESTED): {approve_rate:.1f}%  "
          f"({total - blocking}/{total})")
    return 0


# ---------------------------------------------------------------- github

def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def cmd_github(args: argparse.Namespace) -> int:
    fields = "number,title,author,createdAt,mergedAt,reviews,comments"
    raw = _run(["gh", "pr", "list", "--state", "merged", "--limit", str(args.limit),
                "--json", fields])
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
        p90 = hours[min(len(hours) - 1, int(0.9 * len(hours)))]
        print(f"time-to-merge: median {median(hours):.1f}h, "
              f"p90 {p90:.1f}h, fastest {hours[0]:.1f}h, slowest {hours[-1]:.1f}h")
    print(f"review submissions: {bot_reviews} bot, {human_reviews} human "
          f"({(bot_reviews + human_reviews) / n:.2f} per PR)")

    authors = _counter(prs, lambda p: (p.get("author") or {}).get("login", "?"))
    _table("Merged PRs by author", authors, n)
    print("\nnote: per-finding severity needs the local ledger (`show`); GitHub only "
          "exposes throughput + review cadence.")
    return 0


# ------------------------------------------------------------------ main

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="append one review to the local ledger")
    rec.add_argument("--reviewer", required=True,
                     help="gittan-review | coderabbit | code-review-ultra | ...")
    rec.add_argument("--verdict", required=True,
                     help="APPROVE | APPROVE_WITH_COMMENTS | CHANGES_REQUESTED")
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
    gh.set_defaults(func=cmd_github)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
