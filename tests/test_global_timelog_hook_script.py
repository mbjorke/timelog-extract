"""Sanity checks for embedded global post-commit hook script."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
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

    def test_resolves_central_worklog_from_project_config(self):
        # Identity comes from timelog_projects.json, not from the repo path.
        self.assertIn("timelog_projects.json", HOOK_BODY)
        self.assertIn('GITTAN_HOOK_REPO="$REPO_BASENAME"', HOOK_BODY)
        self.assertIn('"$CONFIGURED_CANDIDATE" == "TIMELOG.md"', HOOK_BODY)
        self.assertIn('TIMELOG_FILE="$PROJECT_WORKLOG"', HOOK_BODY)

    def test_never_derives_worklog_name_from_path_hash(self):
        # Regression: path-derived ids split one project across worktrees and
        # moved repos, and diverged from the documented <project_id>.md model.
        self.assertNotIn("REPO_HASH", HOOK_BODY)
        self.assertNotIn("shasum", HOOK_BODY)
        self.assertNotIn("${REPO_ID}.md", HOOK_BODY)

    def test_central_worklog_is_used_even_when_missing(self):
        # Regression: an [[ -f ]] guard here made commits fall back to the
        # deprecated repo-local TIMELOG.md, silently starving central worklogs.
        self.assertNotIn('if [[ -f "$PROJECT_WORKLOG" ]]', HOOK_BODY)
        fallback_idx = HOOK_BODY.index('PROJECT_WORKLOG="$HOME/.gittan/worklogs/${REPO_BASENAME}.md"')
        assign_idx = HOOK_BODY.index('TIMELOG_FILE="$PROJECT_WORKLOG"')
        self.assertLess(fallback_idx, assign_idx)

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

    @unittest.skipUnless(sys.platform == "darwin", "zsh hook smoke uses macOS path canonicalization")
    def test_resolver_runs_under_zsh_with_set_u(self):
        """The config lookup must survive `set -euo pipefail` and a miss."""
        zsh = shutil.which("zsh")
        if not zsh:
            self.skipTest("zsh not found")
        start = HOOK_BODY.index('PROJECT_WORKLOG="$(GITTAN_HOOK_REPO=')
        end = HOOK_BODY.index('if [[ -z "${CONFIGURED_CANDIDATE:-}"')
        resolver = textwrap.dedent(HOOK_BODY[start:end])
        snippet = 'set -euo pipefail\nROOT_DIR="${1:?}"\nREPO_BASENAME="${ROOT_DIR##*/}"\n' + resolver + '\ntest -n "$PROJECT_WORKLOG"\nprint -r -- "$PROJECT_WORKLOG"\n'
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample-repo"
            repo.mkdir()
            (Path(tmp) / "cfg.json").write_text(
                json.dumps({"projects": [{"name": "sample-repo", "project_id": "sample-repo"}]}),
                encoding="utf-8",
            )
            env = {**os.environ, "GITTAN_PROJECTS_CONFIG": str(Path(tmp) / "cfg.json")}
            proc = subprocess.run(
                [zsh, "-c", snippet, "zsh", str(repo.resolve())],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertTrue(proc.stdout.strip().endswith("worklogs/sample-repo.md"), proc.stdout)
            self.assertNotIn("-", Path(proc.stdout.strip()).stem[len("sample-repo"):])


if __name__ == "__main__":
    unittest.main()
