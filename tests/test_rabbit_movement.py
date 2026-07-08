"""Tests for the rabbit_loop.sh working-tree movement classifier.

The classifier decides whether a multi-minute review is still trustworthy:
  STABLE    same branch + HEAD           -> verdict valid
  ADVANCED  same branch, HEAD advanced   -> auto-commit landed, re-review
  MOVED     branch switched / diverged   -> collision, void
  WORKSPACE gitbutler/* branch           -> lane churn expected, do not void
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rabbit_loop.sh"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _classify(cwd: Path, start_branch: str, start_sha: str) -> str:
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--internal-classify-movement", start_branch, start_sha],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout.strip()


class RabbitMovementTests(unittest.TestCase):
    def setUp(self):
        if not SCRIPT.is_file():
            self.skipTest("rabbit_loop.sh missing")
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "checkout", "-q", "-b", "task/feature")
        _git(self.repo, "config", "user.email", "t@test")
        _git(self.repo, "config", "user.name", "t")
        _git(self.repo, "config", "core.hooksPath", "/dev/null")
        (self.repo / "a.txt").write_text("1\n", encoding="utf-8")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "commit", "-q", "-m", "c1")
        self.start_sha = _git(self.repo, "rev-parse", "HEAD")

    def tearDown(self):
        self._tmp.cleanup()

    def test_stable_when_nothing_moves(self):
        self.assertEqual(_classify(self.repo, "task/feature", self.start_sha), "STABLE")

    def test_advanced_on_same_branch_commit(self):
        (self.repo / "a.txt").write_text("2\n", encoding="utf-8")
        _git(self.repo, "commit", "-aqm", "c2")
        self.assertEqual(_classify(self.repo, "task/feature", self.start_sha), "ADVANCED")

    def test_moved_on_branch_switch(self):
        _git(self.repo, "checkout", "-q", "-b", "task/other")
        self.assertEqual(_classify(self.repo, "task/feature", self.start_sha), "MOVED")

    def test_moved_on_divergent_history(self):
        # Build an orphan commit (not a descendant of start), then hard-reset the
        # original branch onto it — same branch name, but HEAD is now unrelated.
        _git(self.repo, "checkout", "-q", "--orphan", "orphanwt")
        (self.repo / "b.txt").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "b.txt")
        _git(self.repo, "commit", "-q", "-m", "orphan")
        orphan_sha = _git(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "checkout", "-q", "task/feature")
        _git(self.repo, "reset", "--hard", "-q", orphan_sha)
        self.assertEqual(_classify(self.repo, "task/feature", self.start_sha), "MOVED")

    def test_workspace_branch_never_voids(self):
        _git(self.repo, "checkout", "-q", "-b", "gitbutler/workspace")
        (self.repo / "a.txt").write_text("3\n", encoding="utf-8")
        _git(self.repo, "commit", "-aqm", "lane commit")
        # Even though HEAD moved, a gitbutler/* branch classifies as WORKSPACE, not MOVED.
        self.assertEqual(
            _classify(self.repo, "gitbutler/workspace", self.start_sha), "WORKSPACE"
        )


if __name__ == "__main__":
    unittest.main()
