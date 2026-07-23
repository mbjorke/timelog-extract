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
        start = HOOK_BODY.index('GITTAN_HOOK_BRANCH="$(git rev-parse')
        end = HOOK_BODY.index('if [[ -z "${CONFIGURED_CANDIDATE:-}"')
        resolver = textwrap.dedent(HOOK_BODY[start:end])
        snippet = 'set -euo pipefail\nROOT_DIR="${1:?}"\nREPO_BASENAME="${ROOT_DIR##*/}"\n' + resolver + '\ntest -n "$PROJECT_WORKLOG"\nprint -r -- "$PROJECT_WORKLOG"\n'
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample-repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "--allow-empty", "-m", "initial commit"], cwd=repo, capture_output=True)
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

    def test_resolver_writes_to_shadow_log_when_enabled(self):
        """When GITTAN_HOOK_SUBJECT is set and shadow_log is enabled, write the event."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home_dir = tmp_path / "home"
            home_dir.mkdir()
            gittan_dir = home_dir / ".gittan"
            gittan_dir.mkdir()

            cfg_path = gittan_dir / "timelog_projects.json"
            cfg_path.write_text(
                json.dumps({
                    "shadow_log": "on",
                    "projects": [
                        {"name": "test-repo", "project_id": "test-project"}
                    ]
                }),
                encoding="utf-8",
            )

            from core.global_timelog_hook_script import _RESOLVER_PY
            env = {
                "GITTAN_PROJECTS_CONFIG": str(cfg_path),
                "GITTAN_HOOK_REPO": "test-repo",
                "GITTAN_HOOK_SUBJECT": "feat: amazing feature",
                "GITTAN_HOOK_BRANCH": "task/feature-1",
                "GITTAN_HOOK_HASH": "12345678abcdef",
                "HOME": str(home_dir),
                "PYTHONPATH": os.environ.get("PYTHONPATH", "") + os.pathsep + str(Path(__file__).parent.parent.resolve()),
            }

            proc = subprocess.run(
                [sys.executable, "-c", _RESOLVER_PY],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertIn("worklogs/test-project.md", proc.stdout)

            events_dir = gittan_dir / "evidence" / "events"
            self.assertTrue(events_dir.is_dir())

            jsonl_files = list(events_dir.glob("*.jsonl"))
            self.assertEqual(len(jsonl_files), 1)

            records = [json.loads(line) for line in jsonl_files[0].read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["source"], "git-commit")
            from core.sources import canonical_source_name
            self.assertEqual(canonical_source_name(records[0]["source"]), "Git commits")
            self.assertEqual(records[0]["project_at_capture"], "test-project")
            self.assertIn("[test-repo:task/feature-1] feat: amazing feature", records[0]["detail"])
            self.assertEqual(records[0]["source_provenance"]["repo"], "test-repo")
            self.assertEqual(records[0]["source_provenance"]["branch"], "task/feature-1")
            self.assertEqual(records[0]["source_provenance"]["subject"], "feat: amazing feature")
            self.assertEqual(records[0]["source_provenance"]["commit"], "12345678abcdef")

    def test_resolver_writes_to_capture_errors_on_failure(self):
        """When shadow log capture fails, write to capture-errors.jsonl."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home_dir = tmp_path / "home"
            home_dir.mkdir()
            gittan_dir = home_dir / ".gittan"
            gittan_dir.mkdir()

            # Make the evidence directory a file so that write/mkdir fails!
            evidence_file = gittan_dir / "evidence"
            evidence_file.touch()

            cfg_path = gittan_dir / "timelog_projects.json"
            cfg_path.write_text(
                json.dumps({
                    "shadow_log": "on",
                    "projects": [
                        {"name": "test-repo", "project_id": "test-project"}
                    ]
                }),
                encoding="utf-8",
            )

            from core.global_timelog_hook_script import _RESOLVER_PY
            env = {
                "GITTAN_PROJECTS_CONFIG": str(cfg_path),
                "GITTAN_HOOK_REPO": "test-repo",
                "GITTAN_HOOK_SUBJECT": "feat: amazing feature",
                "GITTAN_HOOK_BRANCH": "task/feature-1",
                "GITTAN_HOOK_HASH": "12345678abcdef",
                "HOME": str(home_dir),
                "PYTHONPATH": os.environ.get("PYTHONPATH", "") + os.pathsep + str(Path(__file__).parent.parent.resolve()),
            }

            proc = subprocess.run(
                [sys.executable, "-c", _RESOLVER_PY],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            err_file = home_dir / ".gittan" / "capture-errors.jsonl"
            self.assertTrue(err_file.exists())
            errors = [json.loads(line) for line in err_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(errors), 1)
            self.assertIn("Not a directory", errors[0]["error"])
            self.assertEqual(errors[0]["source"], "git-commit")


if __name__ == "__main__":
    unittest.main()
