"""The Claude Code plugin's fixture must be what the generator produces today.

The fixture is a real report over central worklogs the post-commit hook wrote
in a mock home. If the hook's worklog layout or the truth payload changes, the
plugin's tests would keep passing against a stale picture; this catches that.
"""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build_claude_plugin_fixture.py"


@unittest.skipUnless(shutil.which("zsh") and shutil.which("git"), "hook runs under zsh; needs git")
class ClaudePluginFixtureTest(unittest.TestCase):
    def test_fixture_is_current(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
