"""Tests for `rabbit_loop.sh --author-gate`: only verified internal-authored,
same-repo PRs are auto-merge-eligible. Fork/external PRs are BLOCKED so an
outside contributor's PR can never auto-merge (incident: external fork PR #N).

The gate decides on gh metadata only and never runs PR code; the stub models
`gh pr view <pr> --json author,isCrossRepository`.
"""

from __future__ import annotations

import os
import stat
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rabbit_loop.sh"

_GH_STUB = """#!/usr/bin/env bash
if [[ "$1" != "pr" || "$2" != "view" ]]; then
  echo "unexpected gh invocation: $*" >&2
  exit 1
fi
if [[ "$*" != *"--json author,isCrossRepository"* ]]; then
  echo "expected --json author,isCrossRepository in: $*" >&2
  exit 1
fi
pr_num="${3:-}"
if [[ -z "$pr_num" || ! "$pr_num" =~ ^[1-9][0-9]*$ ]]; then
  echo "invalid pr in gh pr view: '$pr_num'" >&2
  exit 1
fi
if [[ "${GH_STUB_FAIL:-0}" == "1" ]]; then exit 1; fi
if [[ -z "${GH_STUB_AUTHOR+x}" ]]; then author="someone"; else author="$GH_STUB_AUTHOR"; fi
if [[ -z "${GH_STUB_FORK+x}" ]]; then fork="false"; else fork="$GH_STUB_FORK"; fi
printf '%s\\t%s\\n' "$author" "$fork"
exit 0
"""


class RabbitAuthorGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        gh = Path(self._tmp.name) / "gh"
        gh.write_text(_GH_STUB, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{self._tmp.name}:{self.env.get('PATH', '')}"

    def _run(self, *, author="mbjorke", fork="false", fail="0", pr="1", allow=None):
        env = dict(self.env)
        env["GH_STUB_AUTHOR"] = author
        env["GH_STUB_FORK"] = fork
        env["GH_STUB_FAIL"] = fail
        if allow is not None:
            env["GITTAN_INTERNAL_AUTHORS"] = allow
        else:
            env.pop("GITTAN_INTERNAL_AUTHORS", None)
        args = ["bash", str(SCRIPT), "--author-gate"]
        if pr:
            args += ["--pr", pr]
        return subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)

    def test_internal_same_repo_author_is_clear(self):
        p = self._run(author="mbjorke", fork="false")
        self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)
        self.assertIn("AUTHOR_GATE: INTERNAL", p.stdout)

    def test_fork_pr_is_blocked_regardless_of_author(self):
        p = self._run(author="mbjorke", fork="true")
        self.assertEqual(p.returncode, 1)
        self.assertIn("fork", p.stdout.lower())
        self.assertIn("BLOCKED", p.stdout)

    def test_unknown_same_repo_author_is_blocked(self):
        p = self._run(author="unknown-author", fork="false")
        self.assertEqual(p.returncode, 1)
        self.assertIn("not an allowlisted internal identity", p.stdout)

    def test_allowlist_is_overridable(self):
        p = self._run(author="internal-author", fork="false", allow="internal-author")
        self.assertEqual(p.returncode, 0)
        self.assertIn("INTERNAL", p.stdout)

    def test_metadata_query_failure_fails_closed(self):
        p = self._run(fail="1")
        self.assertEqual(p.returncode, 1)
        self.assertIn("fail closed", p.stdout.lower())

    def test_missing_pr_number_fails_closed(self):
        p = self._run(pr="")
        self.assertEqual(p.returncode, 1)
        self.assertIn("no PR number", p.stdout)

    def test_invalid_pr_number_non_numeric_fails_closed(self):
        p = self._run(pr="not-a-number")
        self.assertEqual(p.returncode, 1)
        self.assertIn("invalid PR number", p.stdout)

    def test_empty_author_fails_closed(self):
        p = self._run(author="", fork="false")
        self.assertEqual(p.returncode, 1)
        self.assertIn("empty author login", p.stdout)

    def test_fork_not_explicitly_false_fails_closed(self):
        p = self._run(author="mbjorke", fork="")
        self.assertEqual(p.returncode, 1)
        self.assertIn("not explicitly same-repo", p.stdout)


if __name__ == "__main__":
    unittest.main()
