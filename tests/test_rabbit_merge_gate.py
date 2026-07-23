"""Tests for rabbit_loop.sh --merge-gate.

The gate is the last check before `gh pr merge`. CLEAR requires BOTH a verified
zero unresolved review threads AND positive proof an independent critic reviewed
(a non-author review, a CodeRabbit/Qodo summary comment, or a converged.ack for
the PR head). It must BLOCK on unresolved threads, on an unverifiable query
(fail closed), when no PR resolves, and when no independent review has landed yet.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rabbit_loop.sh"

# Stub gh: answers the exact calls merge_gate() + _pr_review_signals() make. The
# stub ignores each call's `--jq` and echoes the already-reduced value the script
# expects, routed by argument shape. Driven by env vars:
#   GH_STUB_THREADS   `gh api graphql` stdout ("<unresolved-count>\n<hasNextPage>")
#   GH_STUB_API_FAIL  "1" -> the graphql threads query exits 1 (stderr GH_STUB_ERR)
#   GH_STUB_PR        `gh pr view --json number` (empty -> exit 1, "no PR")
#   GH_STUB_REVIEWS   review-signal: non-author review count (default "0")
#   GH_STUB_COMMENTS  review-signal: CodeRabbit/Qodo summary-comment count (default "0")
#   GH_STUB_HEAD      `gh pr view --json headRefOid` (default empty -> ack skipped)
#   GH_STUB_SIG_FAIL  "1" -> the reviews+comments signal queries exit 1
#   GH_STUB_ERR       stderr emitted on a failing call
_GH_STUB = """#!/usr/bin/env bash
args="$*"
case "$1" in
  repo)
    case "$args" in
      *".owner.login"*) echo "stub-owner" ;;
      *) echo "stub-repo" ;;
    esac
    ;;
  pr)
    case "$args" in
      *"--json author,isCrossRepository"*)
        if [[ -z "${GH_STUB_AUTHOR+x}" ]]; then author="mbjorke"; else author="$GH_STUB_AUTHOR"; fi
        if [[ -z "${GH_STUB_FORK+x}" ]]; then fork="false"; else fork="$GH_STUB_FORK"; fi
        printf '%s\\t%s\\n' "$author" "$fork"
        exit 0 ;;
      *headRefOid*) printf '%s\\n' "${GH_STUB_HEAD:-}" ;;
      *author*)     printf '%s\\n' "${GH_STUB_AUTHOR:-pr-author}" ;;
      *)
        if [[ -z "${GH_STUB_PR:-}" ]]; then
          echo "${GH_STUB_ERR:-}" >&2
          exit 1
        fi
        echo "$GH_STUB_PR"
        ;;
    esac
    ;;
  api)
    case "$args" in
      *graphql*)
        if [[ "${GH_STUB_API_FAIL:-0}" == "1" ]]; then
          echo "${GH_STUB_ERR:-}" >&2
          exit 1
        fi
        printf '%s\\n' "${GH_STUB_THREADS:-}"
        ;;
      *reviews*)
        [[ "${GH_STUB_SIG_FAIL:-0}" == "1" ]] && { echo "${GH_STUB_ERR:-}" >&2; exit 1; }
        printf '%s\\n' "${GH_STUB_REVIEWS:-0}"
        ;;
      *comments*)
        [[ "${GH_STUB_SIG_FAIL:-0}" == "1" ]] && { echo "${GH_STUB_ERR:-}" >&2; exit 1; }
        printf '%s\\n' "${GH_STUB_COMMENTS:-0}"
        ;;
      *) exit 1 ;;
    esac
    ;;
  *) exit 1 ;;
esac
"""


class RabbitMergeGateTests(unittest.TestCase):
    def setUp(self):
        if not SCRIPT.is_file():
            self.skipTest("rabbit_loop.sh missing")
        self._tmp = tempfile.TemporaryDirectory()
        stub_dir = Path(self._tmp.name)
        gh = stub_dir / "gh"
        gh.write_text(_GH_STUB, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{stub_dir}:{self.env.get('PATH', '')}"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        run_env = dict(self.env)
        run_env.update(env)
        return subprocess.run(
            ["bash", str(SCRIPT), "--merge-gate", *args],
            cwd=REPO_ROOT,
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_clear_on_zero_threads_with_review(self):
        # 0 unresolved threads AND an independent review (a non-author review).
        proc = self._run("--pr", "5", GH_STUB_THREADS="0\nfalse", GH_STUB_REVIEWS="1")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        self.assertIn("MERGE_GATE: CLEAR", proc.stdout)
        self.assertIn("#5", proc.stdout)

    def test_clear_via_comment_signal(self):
        # A CodeRabbit/Qodo summary comment also counts as an independent review.
        proc = self._run(
            "--pr", "5", GH_STUB_THREADS="0\nfalse", GH_STUB_REVIEWS="0", GH_STUB_COMMENTS="1"
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        self.assertIn("MERGE_GATE: CLEAR", proc.stdout)

    def test_blocked_when_no_independent_review(self):
        # 0 unresolved threads is necessary but NOT sufficient: with no review
        # signal the gate must fail closed (the PR #430 fail-open case).
        proc = self._run(
            "--pr", "5", GH_STUB_THREADS="0\nfalse", GH_STUB_REVIEWS="0", GH_STUB_COMMENTS="0"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MERGE_GATE: BLOCKED", proc.stdout)
        self.assertIn("no independent review", proc.stdout.lower())

    def test_blocked_when_review_signal_query_fails(self):
        # Threads verified clean, but the review-signal query itself failed and no
        # signal was found -> fail closed rather than assume reviewed.
        proc = self._run("--pr", "5", GH_STUB_THREADS="0\nfalse", GH_STUB_SIG_FAIL="1")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MERGE_GATE: BLOCKED", proc.stdout)
        self.assertIn("could not verify independent review", proc.stdout)

    def test_blocked_on_unresolved_threads(self):
        proc = self._run("--pr", "5", GH_STUB_THREADS="2\nfalse")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MERGE_GATE: BLOCKED", proc.stdout)
        self.assertIn("2 unresolved", proc.stdout)

    def test_blocked_fail_closed_when_query_fails(self):
        proc = self._run("--pr", "5", GH_STUB_API_FAIL="1")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MERGE_GATE: BLOCKED", proc.stdout)
        self.assertIn("could not query", proc.stdout)

    def test_blocked_query_failure_surfaces_gh_stderr(self):
        proc = self._run(
            "--pr", "5", GH_STUB_API_FAIL="1", GH_STUB_ERR="HTTP 403: rate limit exceeded"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MERGE_GATE: BLOCKED", proc.stdout)
        self.assertIn("rate limit exceeded", proc.stdout)

    def test_blocked_when_thread_page_overflows(self):
        proc = self._run("--pr", "5", GH_STUB_THREADS="0\ntrue")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MERGE_GATE: BLOCKED", proc.stdout)
        self.assertIn(">100", proc.stdout)

    def test_blocked_when_no_pr_for_branch(self):
        proc = self._run(GH_STUB_PR="", GH_STUB_ERR="no pull requests found for branch")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MERGE_GATE: BLOCKED", proc.stdout)
        self.assertIn("could not resolve an open PR", proc.stdout)
        self.assertIn("no pull requests found", proc.stdout)

    def test_pr_resolved_from_current_branch(self):
        proc = self._run(GH_STUB_PR="7", GH_STUB_THREADS="0\nfalse", GH_STUB_REVIEWS="1")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        self.assertIn("MERGE_GATE: CLEAR (PR #7", proc.stdout)


if __name__ == "__main__":
    unittest.main()
