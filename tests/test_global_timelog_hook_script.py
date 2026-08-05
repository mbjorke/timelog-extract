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

            spool_dir = gittan_dir / "spool"
            self.assertTrue(spool_dir.is_dir())
            spool_files = list(spool_dir.glob("*.json"))
            self.assertEqual(len(spool_files), 1)

            spooled_event = json.loads(spool_files[0].read_text(encoding="utf-8"))
            self.assertEqual(spooled_event["source"], "git-commit")
            self.assertEqual(spooled_event["project"], "test-project")
            self.assertIn("[test-repo:task/feature-1] feat: amazing feature", spooled_event["detail"])
            self.assertEqual(spooled_event["source_provenance"]["repo"], "test-repo")
            self.assertEqual(spooled_event["source_provenance"]["branch"], "task/feature-1")
            self.assertEqual(spooled_event["source_provenance"]["subject"], "feat: amazing feature")
            self.assertEqual(spooled_event["source_provenance"]["commit"], "12345678abcdef")

            events_dir = gittan_dir / "evidence" / "events"
            self.assertFalse(events_dir.exists())

            # Now run capture_events to drain the spool
            from core.evidence_store import capture_events
            capture_events([], home=home_dir)

            # Spool should be empty
            self.assertEqual(len(list(spool_dir.glob("*.json"))), 0)

            # Evidence file should be populated
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

            # Make the spool directory a file so that write/mkdir fails!
            spool_file = gittan_dir / "spool"
            spool_file.touch()

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
            self.assertTrue(any(msg in errors[0]["error"] for msg in ("Not a directory", "File exists")))
            self.assertEqual(errors[0]["source"], "git-commit")

    def test_resolver_works_with_no_core_on_sys_path(self):
        """The post-commit hook must write spool files even when 'core' is not on python path."""
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
                "PYTHONPATH": "",
            }

            proc = subprocess.run(
                [sys.executable, "-c", _RESOLVER_PY],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            spool_dir = gittan_dir / "spool"
            self.assertTrue(spool_dir.is_dir())
            spool_files = list(spool_dir.glob("*.json"))
            self.assertEqual(len(spool_files), 1)

            err_file = home_dir / ".gittan" / "capture-errors.jsonl"
            self.assertFalse(err_file.exists())

    def test_resolver_publishes_spool_file_atomically(self):
        """A spool file must appear complete or not at all.

        The drainer in core/evidence_store.py globs "*.json" and unlinks
        anything it fails to parse, so a reader that catches the hook
        mid-write would delete the commit event instead of keeping it. The
        hook therefore writes to a temp name outside that glob and renames.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home_dir = tmp_path / "home"
            gittan_dir = home_dir / ".gittan"
            gittan_dir.mkdir(parents=True)

            cfg_path = gittan_dir / "timelog_projects.json"
            cfg_path.write_text(
                json.dumps({
                    "shadow_log": "on",
                    "projects": [{"name": "test-repo", "project_id": "test-project"}],
                }),
                encoding="utf-8",
            )

            from core.global_timelog_hook_script import _RESOLVER_PY

            proc = subprocess.run(
                [sys.executable, "-c", _RESOLVER_PY],
                capture_output=True,
                text=True,
                env={
                    "GITTAN_PROJECTS_CONFIG": str(cfg_path),
                    "GITTAN_HOOK_REPO": "test-repo",
                    "GITTAN_HOOK_SUBJECT": "feat: atomic spool",
                    "GITTAN_HOOK_BRANCH": "task/atomic",
                    "GITTAN_HOOK_HASH": "abcdef1234567",
                    "HOME": str(home_dir),
                    "PYTHONPATH": "",
                },
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            spool_dir = gittan_dir / "spool"
            # No temp file survives a successful run, and nothing the drainer
            # would pick up is left behind half-written.
            self.assertEqual([p.name for p in spool_dir.glob("*.tmp")], [])
            spool_files = list(spool_dir.glob("*.json"))
            self.assertEqual(len(spool_files), 1)

            # The one published file parses — which is what the rename guarantees.
            payload = json.loads(spool_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["source_provenance"]["subject"], "feat: atomic spool")

    def test_spool_temp_name_is_outside_the_drainer_glob(self):
        """The temp name must not match the "*.json" pattern the drainer reads."""
        from core.global_timelog_hook_script import _RESOLVER_PY

        self.assertIn("os.replace(temp_file, spool_file)", _RESOLVER_PY)
        temp_name = Path("commit-abcdef.json").with_suffix(".4242.tmp")
        self.assertFalse(temp_name.match("*.json"))


if __name__ == "__main__":
    unittest.main()
