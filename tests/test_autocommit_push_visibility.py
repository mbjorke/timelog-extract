"""The autocommit timer must never fail silently.

A push that reported success by saying nothing let a diverged history fail
every ten minutes for two months while the operator believed their evidence was
backed up. These tests pin the two rules that follow from that: a failure is
always reported, and it never blocks the commit.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gittan_data_autocommit.sh"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.test",
             "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.test"},
    )


class AutocommitPushVisibilityTests(unittest.TestCase):
    def _data_dir(self, stack):
        data = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        _git(data, "init", "-q", "-b", "main")
        (data / "note.md").write_text("first\n", encoding="utf-8")
        _git(data, "add", "-A")
        _git(data, "commit", "-q", "-m", "seed")
        (data / "note.md").write_text("changed\n", encoding="utf-8")
        return data

    def _run(self, data, **env):
        return subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True,
            env={**os.environ, "GITTAN_HOME": str(data),
                 "GITTAN_AUTOCOMMIT_CAPTURE": "0", **env},
        )

    def test_a_failing_push_is_reported(self):
        from contextlib import ExitStack

        with ExitStack() as stack:
            data = self._data_dir(stack)
            # A remote that cannot be reached: the failure must reach the log.
            _git(data, "remote", "add", "origin", str(data / "nowhere.git"))
            result = self._run(data, GITTAN_AUTOCOMMIT_PUSH="1")
            self.assertIn("push failed", result.stderr)

    def test_a_failing_push_does_not_lose_the_commit(self):
        from contextlib import ExitStack

        with ExitStack() as stack:
            data = self._data_dir(stack)
            _git(data, "remote", "add", "origin", str(data / "nowhere.git"))
            self._run(data, GITTAN_AUTOCOMMIT_PUSH="1")
            # The commit is the durable part; a push that cannot reach the
            # remote must not take it down with it.
            log = _git(data, "log", "--oneline").stdout
            self.assertIn("auto:", log)
            self.assertEqual(_git(data, "status", "--porcelain").stdout.strip(), "")

    def test_push_stays_off_unless_asked(self):
        from contextlib import ExitStack

        with ExitStack() as stack:
            data = self._data_dir(stack)
            _git(data, "remote", "add", "origin", str(data / "nowhere.git"))
            result = self._run(data)  # no GITTAN_AUTOCOMMIT_PUSH
            self.assertNotIn("push failed", result.stderr)
            self.assertIn("auto:", _git(data, "log", "--oneline").stdout)

    def test_nothing_to_commit_stays_quiet(self):
        from contextlib import ExitStack

        with ExitStack() as stack:
            data = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            _git(data, "init", "-q", "-b", "main")
            (data / "note.md").write_text("first\n", encoding="utf-8")
            _git(data, "add", "-A")
            _git(data, "commit", "-q", "-m", "seed")
            result = self._run(data, GITTAN_AUTOCOMMIT_PUSH="1")
            self.assertEqual(result.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
