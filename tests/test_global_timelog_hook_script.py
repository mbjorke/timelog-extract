"""Sanity checks for embedded global post-commit hook script."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.global_timelog_hook_script import HOOK_BODY


class GlobalTimelogHookScriptTests(unittest.TestCase):
    def test_uses_portable_shebang_and_grep(self):
        self.assertIn("#!/usr/bin/env zsh", HOOK_BODY)
        self.assertNotIn("#!/bin/zsh", HOOK_BODY)
        self.assertIn("grep -Fxq", HOOK_BODY)
        self.assertNotIn(" rg ", HOOK_BODY)
        self.assertNotIn("rg -Fx", HOOK_BODY)

    def test_supports_absolute_and_tilde_paths(self):
        self.assertIn('if [[ "$TIMELOG_NAME" == /* ]]; then', HOOK_BODY)
        self.assertIn('elif [[ "$TIMELOG_NAME" == ~/* ]]; then', HOOK_BODY)

    def test_prefers_project_scoped_worklog_when_present(self):
        self.assertIn('PROJECT_WORKLOG="$HOME/.gittan/worklogs/${REPO_ID}.md"', HOOK_BODY)
        self.assertIn("awk '{print substr($1,1,8)}'", HOOK_BODY)
        root_idx = HOOK_BODY.index('root_canon="${ROOT_DIR:A}"')
        hash_idx = HOOK_BODY.index('REPO_HASH="$(printf "%s" "$root_canon"')
        self.assertLess(root_idx, hash_idx)
        self.assertIn('"$CONFIGURED_CANDIDATE" == "TIMELOG.md"', HOOK_BODY)
        self.assertIn('TIMELOG_FILE="$PROJECT_WORKLOG"', HOOK_BODY)

    def test_create_if_missing_and_append_only(self):
        # Safety contract: never clobber existing worklogs, only append commit entries.
        self.assertIn('if [[ ! -f "$TIMELOG_FILE" ]]; then', HOOK_BODY)
        self.assertIn('} > "$TIMELOG_FILE"', HOOK_BODY)
        self.assertIn('} >> "$TIMELOG_FILE"', HOOK_BODY)
        self.assertNotIn("cat <<EOF > \"$TIMELOG_FILE\"", HOOK_BODY)

    def test_refuses_unsafe_timelog_filename_and_paths(self):
        self.assertIn("refusing unsafe .. segments", HOOK_BODY)
        self.assertIn('canon="${TIMELOG_FILE:A}"', HOOK_BODY)
        self.assertIn("refusing timelog path outside", HOOK_BODY)

    def test_awk_program_not_double_quoted(self):
        self.assertNotIn('awk "{print substr($1,1,8)}"', HOOK_BODY)
        self.assertIn("awk '{print substr($1,1,8)}'", HOOK_BODY)

    @unittest.skipUnless(sys.platform == "darwin", "zsh hook smoke uses macOS path canonicalization")
    def test_repo_hash_snippet_runs_under_zsh_with_set_u(self):
        zsh = shutil.which("zsh")
        if not zsh:
            self.skipTest("zsh not found")
        snippet = """
set -euo pipefail
ROOT_DIR="${1:?}"
home_canon="${HOME:A}"
root_canon="${ROOT_DIR:A}"
REPO_HASH="$(printf "%s" "$root_canon" | shasum | awk '{print substr($1,1,8)}')"
test -n "$REPO_HASH"
"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample-repo"
            repo.mkdir()
            proc = subprocess.run(
                [zsh, "-c", snippet, "zsh", str(repo.resolve())],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
