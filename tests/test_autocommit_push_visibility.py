"""The autocommit timer must never fail silently.

A push that reported success by saying nothing let a diverged history fail
every ten minutes for two months while the operator believed their evidence was
backed up. These tests pin the two rules that follow from that: a failure is
always reported, and it never blocks the commit.
"""

import os
import stat
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gittan_data_autocommit.sh"

_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@e.test",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@e.test",
}


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        env={**os.environ, **_GIT_IDENTITY},
    )


def _init_repo(path):
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.name", "T")
    _git(path, "config", "user.email", "t@e.test")


def _point_unreachable_origin(data):
    """Set upstream so argument-free `git push` contacts the remote.

    Without branch.main.{remote,merge}, `git push` fails locally with
    "no upstream branch" and never exercises transport or rejection.
    """
    _git(data, "remote", "add", "origin", str(data / "nowhere.git"))
    _git(data, "config", "branch.main.remote", "origin")
    _git(data, "config", "branch.main.merge", "refs/heads/main")


class AutocommitPushVisibilityTests(unittest.TestCase):
    def _data_dir(self, stack):
        data = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        _init_repo(data)
        (data / "note.md").write_text("first\n", encoding="utf-8")
        _git(data, "add", "-A")
        _git(data, "commit", "-q", "-m", "seed")
        (data / "note.md").write_text("changed\n", encoding="utf-8")
        return data

    def _run(self, data, **env):
        return subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True,
            env={**os.environ, **_GIT_IDENTITY, "GITTAN_HOME": str(data),
                 "GITTAN_AUTOCOMMIT_CAPTURE": "0", **env},
        )

    def test_a_failing_push_is_reported(self):
        with ExitStack() as stack:
            data = self._data_dir(stack)
            # A remote that cannot be reached: the failure must reach the log.
            _point_unreachable_origin(data)
            result = self._run(data, GITTAN_AUTOCOMMIT_PUSH="1")
            self.assertEqual(result.returncode, 0)
            self.assertIn("push failed", result.stderr)

    def test_a_failing_push_does_not_lose_the_commit(self):
        with ExitStack() as stack:
            data = self._data_dir(stack)
            _point_unreachable_origin(data)
            result = self._run(data, GITTAN_AUTOCOMMIT_PUSH="1")
            self.assertEqual(result.returncode, 0)
            # The commit is the durable part; a push that cannot reach the
            # remote must not take it down with it.
            log = _git(data, "log", "--oneline").stdout
            self.assertIn("auto:", log)
            self.assertEqual(_git(data, "status", "--porcelain").stdout.strip(), "")

    def test_a_failing_capture_is_reported_and_commit_continues(self):
        with ExitStack() as stack:
            data = self._data_dir(stack)
            bin_dir = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            fake = bin_dir / "gittan"
            fake.write_text(
                "#!/bin/sh\necho capture-boom >&2\nexit 1\n", encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            result = self._run(
                data, GITTAN_AUTOCOMMIT_CAPTURE="1", GITTAN_BIN=str(fake),
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("capture failed", result.stderr)
            self.assertIn("capture-boom", result.stderr)
            self.assertIn("auto:", _git(data, "log", "--oneline").stdout)
            self.assertEqual(_git(data, "status", "--porcelain").stdout.strip(), "")

    def test_push_stays_off_unless_asked(self):
        with ExitStack() as stack:
            data = self._data_dir(stack)
            _point_unreachable_origin(data)
            result = self._run(data)  # no GITTAN_AUTOCOMMIT_PUSH
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("push failed", result.stderr)
            self.assertIn("auto:", _git(data, "log", "--oneline").stdout)

    def test_nothing_to_commit_stays_quiet(self):
        with ExitStack() as stack:
            data = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            _init_repo(data)
            (data / "note.md").write_text("first\n", encoding="utf-8")
            _git(data, "add", "-A")
            _git(data, "commit", "-q", "-m", "seed")
            result = self._run(data, GITTAN_AUTOCOMMIT_PUSH="1")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
