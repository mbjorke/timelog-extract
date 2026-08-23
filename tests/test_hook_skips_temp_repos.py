"""The global commit hook must not record test fixtures as work.

A test suite creates throwaway git repos and commits in them. With the hook
installed globally, every one of those commits was written into the operator's
real evidence ledger, where it can dominate the git-commit source outright. The
commits are real; the work is not.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.global_timelog_hook_script import HOOK_BODY


def _git(cwd, *args, env=None, hooks=None):
    """Run git with hooks pinned to *this* repo.

    The machine this was written on sets a global ``core.hooksPath``, which
    makes git ignore a repo's own ``.git/hooks`` entirely — so a test that
    installs a hook there silently exercises the *installed* hook instead of the
    one under test. Pinning the path is what makes this test about this code.
    """
    base = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.test",
            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.test"}
    prefix = ["-c", f"core.hooksPath={hooks}"] if hooks else []
    return subprocess.run(["git", *prefix, *args], cwd=cwd, capture_output=True, text=True,
                          env={**base, **(env or {})})


class HookSkipsTempReposTests(unittest.TestCase):
    def setUp(self):
        # Without zsh the hook cannot execute at all, and every assertion below
        # would pass on a hook that never ran — coverage for nothing.
        if not shutil.which("zsh"):
            self.skipTest("zsh not found; the hook cannot run")

    def _repo_with_hook(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        _git(root, "init", "-q", "-b", "main")
        hooks = root / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        hook = hooks / "post-commit"
        hook.write_text(HOOK_BODY, encoding="utf-8")
        hook.chmod(0o755)
        return root

    def _commit(self, root: Path, data_dir: Path, **env):
        hooks = root / ".git" / "hooks"
        (root / "f.txt").write_text("x\n", encoding="utf-8")
        _git(root, "add", "-A")
        return _git(root, "commit", "-q", "-m", "seed", hooks=hooks,
                    env={"GITTAN_HOME": str(data_dir), **env})

    def _spooled(self, data_dir: Path) -> int:
        # Any file the hook wrote under the data dir counts: the spool layout is
        # an implementation detail, "it wrote something" is the contract here.
        if not data_dir.exists():
            return 0
        return sum(1 for p in data_dir.rglob("*") if p.is_file())

    def test_a_repo_in_a_temp_dir_records_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            repo = self._repo_with_hook(Path(tmp) / "throwaway")
            self._commit(repo, data)
            self.assertEqual(self._spooled(data), 0)

    def test_the_guard_can_be_overridden_deliberately(self):
        # The hook decides what counts as work; that decision must be
        # reversible by the person whose hours they are.
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            repo = self._repo_with_hook(Path(tmp) / "throwaway")
            result = self._commit(repo, data, GITTAN_HOOK_ALLOW_TEMP="1")
            self.assertEqual(result.returncode, 0, result.stderr)
            # Must be a *recording*, not merely a clean exit: `>= 0` is true of
            # every possible outcome, so it would pass on a broken override.
            self.assertGreater(self._spooled(data), 0)

    def test_the_commit_itself_always_succeeds(self):
        # A hook that refuses to record must never refuse the commit.
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            repo = self._repo_with_hook(Path(tmp) / "throwaway")
            result = self._commit(repo, data)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("seed", _git(repo, "log", "--oneline").stdout)

    def _guard_verdict(self, root: str) -> str:
        """Run just the guard against a synthetic repo root.

        End-to-end is the wrong tool for this one case: it needs a repository
        *outside* every temporary root, and the checkout itself may live under
        one (it does in this sandbox), which would skip the fixture for exactly
        the reason the test is trying to rule out. Lifting the guard is how the
        rest of the hook's guards are tested.
        """
        body = HOOK_BODY
        begin = body.index("# A repository under a temporary directory")
        finish = body.index('GITTAN_CFG_DIR="$GITTAN_DATA_DIR"')
        guard = body[begin:finish]
        snippet = (
            "set -euo pipefail\n"
            # Canonicalised, exactly as the hook does before reaching the
            # guard: without it "/tmp" never matches "/private/tmp" and the
            # guard would look broken when the caller was.
            'root_dir_canon="${${1:?}:A}"\n'
            + guard
            + "\nprint -r -- RECORDED\n"
        )
        result = subprocess.run(
            ["zsh", "-c", snippet, "zsh", root],
            capture_output=True, text=True, env={**os.environ},
        )
        return result.stdout.strip()

    def test_a_name_beginning_with_tmp_outside_a_temp_root_still_records(self):
        # The guard is about *where* a repository is, not what it is called.
        self.assertEqual(
            self._guard_verdict("/Users/someone/work/tmp-real-project"), "RECORDED"
        )

    def test_a_path_inside_a_temp_root_is_skipped(self):
        # The same lifted guard, to show the two verdicts come from one code
        # path rather than from two differently-configured runs.
        self.assertEqual(self._guard_verdict("/private/tmp/throwaway"), "")
        self.assertEqual(self._guard_verdict("/tmp/throwaway"), "")

if __name__ == "__main__":
    unittest.main()
