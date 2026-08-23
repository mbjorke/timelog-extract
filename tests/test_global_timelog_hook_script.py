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
import unittest.mock
from pathlib import Path

from core.global_timelog_hook_script import _RESOLVER_PY, HOOK_BODY


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
        fallback_idx = HOOK_BODY.index('PROJECT_WORKLOG="$GITTAN_DATA_DIR/worklogs/${REPO_BASENAME}.md"')
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

    def _run_guard(self, tmp: Path, repo: Path, data_dir: Path):
        """Run only the hook's early guard; echo REACHED if it falls through."""
        zsh = shutil.which("zsh")
        if not zsh:
            self.skipTest("zsh not found")
        start = HOOK_BODY.index("# Gittan's own data directory is not a project")
        end = HOOK_BODY.index('GITTAN_CFG_DIR="$GITTAN_DATA_DIR"')
        guard = textwrap.dedent(HOOK_BODY[start:end])
        snippet = 'set -euo pipefail\nROOT_DIR="${1:?}"\n' + guard + '\nprint -r -- REACHED\n'
        return subprocess.run(
            [zsh, "-c", snippet, "zsh", str(repo.resolve())],
            capture_output=True, text=True,
            env={
                **os.environ,
                "GITTAN_HOME": str(data_dir.resolve()),
                # These cases exercise the *data-directory* guard, using
                # throwaway repos to do it. The temp guard that now shares this
                # block would exit first and hide what they are testing, so they
                # opt in explicitly — which is what the escape hatch is for.
                "GITTAN_HOOK_ALLOW_TEMP": "1",
            },
        )

    def test_hook_skips_the_gittan_data_directory(self):
        # GH-535: the autocommit runbook makes the data dir a git repo, so without
        # this guard every auto-commit fires the hook, which writes a spool event
        # and a worklog *inside* that directory, which the next tick commits, which
        # fires the hook again — forever, fabricating attributed activity each time.
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "gittan-data"
            data.mkdir()
            proc = self._run_guard(Path(tmp), data, data)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertNotIn("REACHED", proc.stdout)

    def test_hook_skips_a_repo_nested_inside_the_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "gittan-data"
            nested = data / "worklogs" / "inner"
            nested.mkdir(parents=True)
            proc = self._run_guard(Path(tmp), nested, data)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertNotIn("REACHED", proc.stdout)

    def test_hook_still_runs_for_an_ordinary_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "gittan-data"
            data.mkdir()
            repo = Path(tmp) / "some-project"
            repo.mkdir()
            proc = self._run_guard(Path(tmp), repo, data)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("REACHED", proc.stdout)

    def test_hook_does_not_skip_a_sibling_sharing_a_name_prefix(self):
        # "gittan-data-backup" is not inside "gittan-data"; prefix matching must
        # respect path boundaries.
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "gittan-data"
            data.mkdir()
            sibling = Path(tmp) / "gittan-data-backup"
            sibling.mkdir()
            proc = self._run_guard(Path(tmp), sibling, data)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("REACHED", proc.stdout)

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

    def _spool_once(
        self, home_dir: Path, *, repo: str, commit: str, subject: str, repo_path: str = ""
    ) -> None:
        gittan_dir = home_dir / ".gittan"
        gittan_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = gittan_dir / "timelog_projects.json"
        cfg_path.write_text(
            json.dumps({
                "shadow_log": "on",
                "projects": [{"name": repo, "project_id": repo}],
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
                "GITTAN_HOOK_REPO": repo,
                "GITTAN_HOOK_REPO_PATH": repo_path,
                "GITTAN_HOOK_SUBJECT": subject,
                "GITTAN_HOOK_BRANCH": "main",
                "GITTAN_HOOK_HASH": commit,
                "HOME": str(home_dir),
                "PYTHONPATH": "",
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_same_commit_hash_in_two_repos_keeps_both_events(self):
        """Two repos can produce byte-identical commit objects, hence one hash.

        Naming the spool file by hash alone made the second os.replace()
        overwrite the first, and that commit never reached the evidence store.
        """
        shared_hash = "0123456789abcdef0123456789abcdef01234567"
        with tempfile.TemporaryDirectory() as tmp:
            home_dir = Path(tmp) / "home"
            self._spool_once(home_dir, repo="repo-alpha", commit=shared_hash, subject="first")
            self._spool_once(home_dir, repo="repo-beta", commit=shared_hash, subject="second")

            spool_files = sorted((home_dir / ".gittan" / "spool").glob("*.json"))
            self.assertEqual(len(spool_files), 2, "one commit was overwritten by the other")
            subjects = {
                json.loads(p.read_text(encoding="utf-8"))["source_provenance"]["subject"]
                for p in spool_files
            }
            self.assertEqual(subjects, {"first", "second"})

    def test_same_basename_in_two_directories_keeps_both_events(self):
        """`~/work/api` and `~/personal/api` are different repos with one name.

        The hook passes only the basename as GITTAN_HOOK_REPO, so digesting
        that left both checkouts sharing a spool file; with a shared commit
        hash the second os.replace() dropped the first commit silently.
        """
        shared_hash = "1122334455667788112233445566778811223344"
        with tempfile.TemporaryDirectory() as tmp:
            home_dir = Path(tmp) / "home"
            self._spool_once(
                home_dir, repo="api", commit=shared_hash, subject="work",
                repo_path=str(Path(tmp) / "work" / "api"),
            )
            self._spool_once(
                home_dir, repo="api", commit=shared_hash, subject="personal",
                repo_path=str(Path(tmp) / "personal" / "api"),
            )

            spool_files = sorted((home_dir / ".gittan" / "spool").glob("*.json"))
            self.assertEqual(len(spool_files), 2, "same-named repos shared one spool file")
            subjects = {
                json.loads(p.read_text(encoding="utf-8"))["source_provenance"]["subject"]
                for p in spool_files
            }
            self.assertEqual(subjects, {"work", "personal"})

    def test_same_repo_path_still_dedupes_one_commit(self):
        """Scoping by path must not defeat the idempotency the hash provides."""
        commit = "9988776655443322998877665544332299887766"
        with tempfile.TemporaryDirectory() as tmp:
            home_dir = Path(tmp) / "home"
            repo_path = str(Path(tmp) / "work" / "api")
            for _ in range(2):
                self._spool_once(
                    home_dir, repo="api", commit=commit, subject="one commit",
                    repo_path=repo_path,
                )

            spool_files = list((home_dir / ".gittan" / "spool").glob("*.json"))
            self.assertEqual(len(spool_files), 1, "re-spooling one commit must not duplicate it")

    def test_hook_passes_the_repo_path_for_spool_scoping_only(self):
        """The path reaches the spool key, never the worklog filename."""
        self.assertIn('GITTAN_HOOK_REPO_PATH="$ROOT_DIR"', HOOK_BODY)
        self.assertIn('GITTAN_HOOK_REPO_PATH', _RESOLVER_PY)
        # Identity still comes from the basename via timelog_projects.json.
        self.assertIn('PROJECT_WORKLOG="$GITTAN_DATA_DIR/worklogs/${REPO_BASENAME}.md"', HOOK_BODY)

    def test_respooling_the_same_commit_stays_idempotent(self):
        """The hash in the name is load-bearing — a pid suffix would break this.

        Two files for one commit would carry different `timestamp` values, and
        the dedup fingerprint is (source, observed_at, detail), so both would
        survive into the store as separate records for a single commit.
        """
        commit = "fedcba9876543210fedcba9876543210fedcba98"
        with tempfile.TemporaryDirectory() as tmp:
            home_dir = Path(tmp) / "home"
            self._spool_once(home_dir, repo="repo-alpha", commit=commit, subject="same commit")
            self._spool_once(home_dir, repo="repo-alpha", commit=commit, subject="same commit")

            spool_files = list((home_dir / ".gittan" / "spool").glob("*.json"))
            self.assertEqual(len(spool_files), 1, "re-spooling one commit must not duplicate it")

    def test_repo_names_that_normalize_alike_stay_distinct(self):
        """norm() is lossy: "repo-a" and "repo_a" collapse to one slug.

        With a shared commit hash that made the second os.replace() overwrite
        the first, which is the bug the repo scoping was meant to remove.
        """
        shared = "abcdef0123456789abcdef0123456789abcdef01"
        with tempfile.TemporaryDirectory() as tmp:
            home_dir = Path(tmp) / "home"
            self._spool_once(home_dir, repo="repo-a", commit=shared, subject="dash")
            self._spool_once(home_dir, repo="repo_a", commit=shared, subject="underscore")

            spool_files = sorted((home_dir / ".gittan" / "spool").glob("*.json"))
            self.assertEqual(len(spool_files), 2, "lossy normalisation lost one event")
            subjects = {
                json.loads(p.read_text(encoding="utf-8"))["source_provenance"]["subject"]
                for p in spool_files
            }
            self.assertEqual(subjects, {"dash", "underscore"})

    def test_spool_follows_gittan_home_so_capture_events_can_drain_it(self):
        """$GITTAN_HOME *is* the data dir for the store, so the hook must use it.

        Writing to $HOME/.gittan while capture_events() drains $GITTAN_HOME left
        the commit event stranded with nothing reporting it.
        """
        from core.evidence_store import capture_events, spool_dir

        with tempfile.TemporaryDirectory() as tmp:
            home_dir = Path(tmp) / "home"
            state_root = Path(tmp) / "elsewhere"
            gittan_dir = home_dir / ".gittan"
            gittan_dir.mkdir(parents=True)
            cfg_path = gittan_dir / "timelog_projects.json"
            cfg_path.write_text(
                json.dumps({"shadow_log": "on",
                            "projects": [{"name": "repo-alpha", "project_id": "repo-alpha"}]}),
                encoding="utf-8",
            )

            from core.global_timelog_hook_script import _RESOLVER_PY

            proc = subprocess.run(
                [sys.executable, "-c", _RESOLVER_PY],
                capture_output=True, text=True,
                env={
                    "GITTAN_PROJECTS_CONFIG": str(cfg_path),
                    "GITTAN_HOOK_REPO": "repo-alpha",
                    "GITTAN_HOOK_SUBJECT": "routed by GITTAN_HOME",
                    "GITTAN_HOOK_BRANCH": "main",
                    "GITTAN_HOOK_HASH": "1111111111111111111111111111111111111111",
                    "HOME": str(home_dir),
                    "GITTAN_HOME": str(state_root),
                    "PYTHONPATH": "",
                },
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            self.assertEqual(
                list((state_root / "spool").glob("*.json")).__len__(), 1,
                "the hook must write where the store looks",
            )
            self.assertFalse((gittan_dir / "spool").exists(), "not under $HOME/.gittan")

            # And the store actually finds it.
            with unittest.mock.patch.dict(os.environ, {"GITTAN_HOME": str(state_root)}):
                self.assertEqual(spool_dir(), state_root / "spool")
                result = capture_events([])
            self.assertGreaterEqual(result.get("appended", 0), 1)

    def test_spool_temp_name_is_outside_the_drainer_glob(self):
        """The temp name must not match the "*.json" pattern the drainer reads."""
        from core.global_timelog_hook_script import _RESOLVER_PY

        self.assertIn("os.replace(temp_file, spool_file)", _RESOLVER_PY)
        temp_name = Path("commit-abcdef.json").with_suffix(".4242.tmp")
        self.assertFalse(temp_name.match("*.json"))


if __name__ == "__main__":
    unittest.main()
