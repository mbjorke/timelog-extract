"""Tests for `rabbit_loop.sh --agent-gate`: which agent produced the branch.

Distinct from --author-gate, which answers internal-vs-fork. The PR author
field cannot answer this on this repo — Jules, Cursor and Claude all push
through the maintainer's credentials, so every PR reports the same login.
Commit authorship can, so the gate reads that.

The gate must pass only when EVERY commit is the expected agent's. "Any commit
by the agent" would let a branch a second agent has also worked on through, and
that is precisely the case a human should look at.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rabbit_loop.sh"

JULES = "google-labs-jules[bot]"


class RabbitAgentGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "base@example.test")
        self._git("config", "user.name", "Base")
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        self._git("add", "seed.txt")
        self._git("commit", "-q", "-m", "seed")
        # `origin/main` without a real remote: the gate only needs the ref to resolve.
        self._git("update-ref", "refs/remotes/origin/main", "HEAD")

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True
        ).stdout

    def _commit_as(self, author: str, filename: str) -> None:
        (self.repo / filename).write_text(f"{author}\n", encoding="utf-8")
        self._git("add", filename)
        env = dict(os.environ)
        env["GIT_AUTHOR_NAME"] = author
        env["GIT_AUTHOR_EMAIL"] = "agent@example.test"
        subprocess.run(
            ["git", "commit", "-q", "-m", f"work by {author}"],
            cwd=self.repo, capture_output=True, text=True, check=True, env=env,
        )

    def _gate(self, *extra: str, expected_author: str | None = None):
        env = dict(os.environ)
        env.pop("GITTAN_AGENT_AUTHOR", None)
        if expected_author is not None:
            env["GITTAN_AGENT_AUTHOR"] = expected_author
        # Keep gh off PATH: with no --pr the gate is pure git, and an ambient gh
        # must not change the verdict.
        env["PATH"] = "/usr/bin:/bin"
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--agent-gate", *extra],
            cwd=self.repo, capture_output=True, text=True, env=env,
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()

    def test_single_expected_agent_passes(self):
        self._commit_as(JULES, "a.txt")
        self._commit_as(JULES, "b.txt")
        code, out = self._gate()
        self.assertEqual(code, 0, msg=out)
        self.assertIn(f"AGENT_GATE: {JULES}", out)
        self.assertIn("2 commit(s)", out)

    def test_mixed_authors_are_blocked(self):
        self._commit_as(JULES, "a.txt")
        self._commit_as("Claude", "b.txt")
        code, out = self._gate()
        self.assertEqual(code, 1, msg=out)
        self.assertIn("AGENT_GATE: BLOCKED", out)
        self.assertIn("2 authors", out)
        self.assertIn("Claude", out)

    def test_mixed_is_blocked_even_when_the_agent_wrote_most_of_it(self):
        """A single foreign commit is enough — majority does not carry the branch."""
        for name in ("a.txt", "b.txt", "c.txt"):
            self._commit_as(JULES, name)
        self._commit_as("Claude", "d.txt")
        code, out = self._gate()
        self.assertEqual(code, 1, msg=out)
        self.assertIn("AGENT_GATE: BLOCKED", out)

    def test_other_single_agent_is_blocked(self):
        self._commit_as("Cursor Agent", "a.txt")
        code, out = self._gate()
        self.assertEqual(code, 1, msg=out)
        self.assertIn("authored by 'Cursor Agent'", out)
        self.assertIn(f"expected '{JULES}'", out)

    def test_expected_author_is_overridable(self):
        self._commit_as("Cursor Agent", "a.txt")
        code, out = self._gate(expected_author="Cursor Agent")
        self.assertEqual(code, 0, msg=out)
        self.assertIn("AGENT_GATE: Cursor Agent", out)

    def test_no_commits_fails_closed(self):
        code, out = self._gate()
        self.assertEqual(code, 1, msg=out)
        self.assertIn("no commits", out)

    def test_missing_base_ref_fails_closed(self):
        self._commit_as(JULES, "a.txt")
        code, out = self._gate("--base", "origin/does-not-exist")
        self.assertEqual(code, 1, msg=out)
        self.assertIn("base ref", out)

    def test_invalid_pr_number_fails_closed(self):
        self._commit_as(JULES, "a.txt")
        code, out = self._gate("--pr", "abc")
        self.assertEqual(code, 1, msg=out)
        self.assertIn("invalid PR number", out)


if __name__ == "__main__":
    unittest.main()
