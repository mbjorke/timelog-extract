"""The Claude Code plugin's fixture must be what the generator produces today.

The fixture is a real report over central worklogs the post-commit hook wrote
in a mock home. If the hook's worklog layout or the truth payload changes, the
plugin's tests would keep passing against a stale picture; this catches that.
"""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build_claude_plugin_fixture.py"


@unittest.skipUnless(shutil.which("zsh") and shutil.which("git"), "hook runs under zsh; needs git")
class ClaudePluginFixtureTest(unittest.TestCase):
    def _check(self, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )

    def test_fixture_is_current(self):
        proc = self._check()
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_caller_environment_cannot_leak_into_the_fixture(self):
        # A maintainer's shell: a GitHub login would enable the network source,
        # a config override would replace the mock profiles. Neither may reach
        # the generated fixture, so --check still matches.
        env = {
            **os.environ,
            "GITHUB_USER": "example-login",
            "GITHUB_LOGIN": "example-login",
            "TOGGL_API_TOKEN": "example-token",
            "GITTAN_PROJECTS_CONFIG": str(REPO_ROOT / "does-not-exist.json"),
        }
        proc = self._check(env)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
