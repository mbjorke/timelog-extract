"""Tests for rabbit_loop.sh --merge-gate (unresolved review threads).

The gate is the last check before `gh pr merge`: it must BLOCK when unresolved
review threads exist, when they cannot be verified (fail closed), and when no
PR can be resolved — and only report CLEAR on a verified zero.
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

# Stub gh: answers the exact calls merge_gate() makes, driven by env vars.
#   GH_STUB_THREADS  stdout for `gh api graphql` ("<count>\n<hasNextPage>")
#   GH_STUB_API_FAIL "1" -> `gh api graphql` exits 1 (stderr: GH_STUB_ERR)
#   GH_STUB_PR       stdout for `gh pr view --json number` (empty -> exit 1)
#   GH_STUB_ERR      stderr emitted on the failing call
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
    if [[ -z "${GH_STUB_PR:-}" ]]; then
      echo "${GH_STUB_ERR:-}" >&2
      exit 1
    fi
    echo "$GH_STUB_PR"
    ;;
  api)
    if [[ "${GH_STUB_API_FAIL:-0}" == "1" ]]; then
      echo "${GH_STUB_ERR:-}" >&2
      exit 1
    fi
    printf '%s\\n' "${GH_STUB_THREADS:-}"
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

    def test_clear_on_verified_zero_unresolved(self):
        proc = self._run("--pr", "5", GH_STUB_THREADS="0\nfalse")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        self.assertIn("MERGE_GATE: CLEAR", proc.stdout)
        self.assertIn("#5", proc.stdout)

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
        proc = self._run(GH_STUB_PR="7", GH_STUB_THREADS="0\nfalse")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        self.assertIn("MERGE_GATE: CLEAR (PR #7", proc.stdout)


if __name__ == "__main__":
    unittest.main()
