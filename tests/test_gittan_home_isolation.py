"""One data directory for every store, whether ``$GITTAN_HOME`` is set or not (GH-549).

The observed cache used to ignore ``$GITTAN_HOME`` while config, evidence and the
commit hook honoured it. A sandboxed run therefore merged into the operator's real
``~/.gittan/observed`` — and that merge is keep-max, so nothing undoes it.

Every case here is asserted **twice**: once with ``$GITTAN_HOME`` pointing at a temp
dir, and once with it unset. Only testing the relocated case is what let the default
path regress unnoticed before.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.config import GittanHomeError, canonical_gittan_home, gittan_data_dir
from core.evidence_store import evidence_base_dir, spool_dir
from core.global_timelog_hook_script import HOOK_BODY
from core.global_timelog_machine_setup import (
    gittan_config_dir,
    gittan_filename_file,
    gittan_scope_file,
)
from core.intent_store import intent_path
from core.observed_cache import (
    observed_base_dir,
    observed_hours_by_project_day,
    write_observed_summary,
)
from core.reported_time import reported_base_dir

#: Every store that must move together, mapped back to the data dir it sits in.
#: Name -> callable taking ``home`` and returning the resolved data dir.
STORE_DATA_DIRS = {
    "observed": lambda home: observed_base_dir(home).parent,
    "evidence": lambda home: evidence_base_dir(home).parent,
    "spool": lambda home: spool_dir(home).parent,
    "reported": lambda home: reported_base_dir(home).parent,
    "intent": lambda home: intent_path(home).parent,
}


def _no_gittan_home():
    """Environment with ``$GITTAN_HOME`` explicitly absent."""
    env = dict(os.environ)
    env.pop("GITTAN_HOME", None)
    return mock.patch.dict(os.environ, env, clear=True)


class DataDirResolverTests(unittest.TestCase):
    def test_env_set_makes_that_directory_the_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GITTAN_HOME": tmp}):
                # No ".gittan" segment: $GITTAN_HOME *is* the data dir, matching
                # how core/config.py resolves the projects config.
                self.assertEqual(gittan_data_dir(), Path(tmp))

    def test_env_unset_falls_back_to_the_canonical_home(self):
        with _no_gittan_home():
            self.assertEqual(gittan_data_dir(), canonical_gittan_home())
            self.assertEqual(gittan_data_dir(), Path.home() / ".gittan")

    def test_explicit_home_wins_over_the_environment(self):
        """An explicit ``home`` is a *user* home and is env-independent.

        Tests and CLI callers pass a fake home to build a whole sandbox; letting
        an ambient variable redirect it would put state where the caller cannot
        find it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GITTAN_HOME": "/somewhere/else"}):
                self.assertEqual(gittan_data_dir(Path(tmp)), Path(tmp) / ".gittan")

    def test_env_value_is_user_expanded(self):
        with mock.patch.dict(os.environ, {"GITTAN_HOME": "~/sandbox-dir"}):
            self.assertEqual(gittan_data_dir(), Path.home() / "sandbox-dir")

    def test_an_unresolvable_user_is_refused_not_a_pathlib_crash(self):
        """``Path.expanduser()`` raises RuntimeError here — an opaque failure.

        ``os.path.expanduser`` leaves the value alone, so it reaches the
        absolute-path check and fails with a message naming the variable.
        """
        with mock.patch.dict(os.environ, {"GITTAN_HOME": "~nosuchuser42/x"}):
            with self.assertRaises(GittanHomeError) as ctx:
                gittan_data_dir()
        self.assertIn("GITTAN_HOME", str(ctx.exception))

    def test_a_relative_value_is_refused_with_an_actionable_message(self):
        with mock.patch.dict(os.environ, {"GITTAN_HOME": "data"}):
            with self.assertRaises(GittanHomeError) as ctx:
                gittan_data_dir()
        message = str(ctx.exception)
        self.assertIn("absolute path", message)
        self.assertIn("data", message)

    def test_an_explicit_relative_home_is_still_allowed(self):
        """The ``home`` argument is a caller's deliberate choice, not ambient env.

        Tests and callers pass it directly, so there is no second process to
        disagree with; only the env var carries the cwd hazard.
        """
        self.assertEqual(gittan_data_dir(Path("rel")), Path("rel") / ".gittan")

    def test_blank_env_value_is_ignored(self):
        with mock.patch.dict(os.environ, {"GITTAN_HOME": "   "}):
            self.assertEqual(gittan_data_dir(), canonical_gittan_home())


class EveryStoreAgreesTests(unittest.TestCase):
    """Acceptance 1: every store resolves under one root, in both modes."""

    def test_all_stores_live_under_gittan_home_when_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"GITTAN_HOME": tmp}):
                for name, data_dir_of in STORE_DATA_DIRS.items():
                    with self.subTest(store=name):
                        self.assertEqual(data_dir_of(None), root)

    def test_all_stores_live_under_the_canonical_home_when_unset(self):
        with _no_gittan_home():
            for name, data_dir_of in STORE_DATA_DIRS.items():
                with self.subTest(store=name):
                    self.assertEqual(data_dir_of(None), Path.home() / ".gittan")

    def test_all_stores_follow_an_explicit_home_in_both_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            for env in ({"GITTAN_HOME": str(Path(tmp) / "elsewhere")}, {}):
                patcher = mock.patch.dict(os.environ, env) if env else _no_gittan_home()
                with patcher:
                    for name, data_dir_of in STORE_DATA_DIRS.items():
                        with self.subTest(store=name, env=bool(env)):
                            self.assertEqual(data_dir_of(home), home / ".gittan")


def _report(day: str, project: str):
    """Minimal report whose ``overall_days`` drive ``build_reported_proposals``.

    Same shape as ``tests/test_observed_cache.py`` — one 1h session on one day.
    """
    start = datetime.fromisoformat(f"{day}T10:00:00")
    end = datetime.fromisoformat(f"{day}T11:00:00")
    session = (start, end, [{"project": project, "source": "TIMELOG.md"}])
    return SimpleNamespace(
        overall_days={day: {"sessions": [session]}},
        args=Namespace(min_session=15, min_session_passive=5),
    )


class ObservedCacheIsolationTests(unittest.TestCase):
    """Acceptance 2: a sandboxed run must not touch the real observed cache."""

    def test_write_lands_in_gittan_home_and_leaves_the_default_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "sandbox"
            fake_real_home = Path(tmp) / "real-home"
            real_observed = fake_real_home / ".gittan" / "observed"
            real_observed.mkdir(parents=True)
            existing = real_observed / "2026-06.jsonl"
            existing.write_text(
                json.dumps({"project": "kept", "date": "2026-06-01", "hours": 9.0, "captured_at": ""}) + "\n",
                encoding="utf-8",
            )
            before = sorted((p.name, p.read_bytes()) for p in real_observed.glob("*.jsonl"))

            with mock.patch.object(Path, "home", staticmethod(lambda: fake_real_home)):
                with mock.patch.dict(os.environ, {"GITTAN_HOME": str(sandbox)}):
                    written = write_observed_summary(_report("2026-06-20", "sandboxed"))

            self.assertEqual(written, 1)
            self.assertTrue((sandbox / "observed" / "2026-06.jsonl").is_file())
            after = sorted((p.name, p.read_bytes()) for p in real_observed.glob("*.jsonl"))
            self.assertEqual(before, after, "the real observed cache must be byte-identical")

    def test_write_lands_in_the_canonical_home_when_gittan_home_is_unset(self):
        """The default path is not a special case — it is the one that regressed.

        GH-550's blind spot was covering only the relocated variable, so a fix
        that broke the unset default would have shipped green.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fake_real_home = Path(tmp) / "real-home"
            fake_real_home.mkdir()
            with mock.patch.object(Path, "home", staticmethod(lambda: fake_real_home)):
                with _no_gittan_home():
                    written = write_observed_summary(_report("2026-06-20", "default-home"))
                    self.assertEqual(written, 1)
                    self.assertEqual(
                        observed_hours_by_project_day().get(("default-home", "2026-06-20")), 1.0
                    )
            self.assertTrue((fake_real_home / ".gittan" / "observed" / "2026-06.jsonl").is_file())

    def test_a_sandboxed_run_cannot_read_the_real_cache_either(self):
        """Read and write must resolve to the same root.

        A split — write to the sandbox, read from the real home — would report
        the operator's real hours out of a run that never wrote them, which is
        the disagreement this issue is about.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fake_real_home = Path(tmp) / "real-home"
            real_observed = fake_real_home / ".gittan" / "observed"
            real_observed.mkdir(parents=True)
            (real_observed / "2026-06.jsonl").write_text(
                json.dumps({"project": "real", "date": "2026-06-01", "hours": 9.0, "captured_at": ""}) + "\n",
                encoding="utf-8",
            )
            with mock.patch.object(Path, "home", staticmethod(lambda: fake_real_home)):
                with mock.patch.dict(os.environ, {"GITTAN_HOME": str(Path(tmp) / "sandbox")}):
                    self.assertEqual(observed_hours_by_project_day(), {})
                with _no_gittan_home():
                    self.assertEqual(
                        observed_hours_by_project_day().get(("real", "2026-06-01")), 9.0
                    )


class HookUsesOneDataDirTests(unittest.TestCase):
    """The shell hook body must not split its paths across two roots."""

    def test_shell_paths_route_through_the_data_dir(self):
        self.assertIn('GITTAN_DATA_DIR="${GITTAN_HOME:-}"', HOOK_BODY)
        self.assertIn('GITTAN_CFG_DIR="$GITTAN_DATA_DIR"', HOOK_BODY)
        self.assertIn('PROJECT_WORKLOG="$GITTAN_DATA_DIR/worklogs/${REPO_BASENAME}.md"', HOOK_BODY)

    def test_no_shell_path_hardcodes_the_gittan_directory_under_home(self):
        """``$HOME/.gittan`` may only appear as the fallback inside GITTAN_DATA_DIR.

        Counting occurrences catches a new hardcoded path being added back, which
        is how the scope file and the worklog fallback drifted apart to begin
        with. Comment lines are excluded so prose about the old bug is free.
        """
        code_lines = [
            line for line in HOOK_BODY.splitlines() if not line.lstrip().startswith("#")
        ]
        hits = [line for line in code_lines if "$HOME/.gittan" in line]
        self.assertEqual(
            hits,
            ['[[ -n "${GITTAN_DATA_DIR:-}" ]] || GITTAN_DATA_DIR="$HOME/.gittan"'],
            hits,
        )

    def test_the_path_guard_allows_the_relocated_data_dir(self):
        """Without this, $GITTAN_HOME outside $HOME makes the hook refuse to write.

        The guard exists to stop a crafted timelog_filename escaping to an
        arbitrary path; the data dir is a legitimate destination, so it is
        allowed explicitly rather than by widening the check.
        """
        self.assertIn('"$canon" != "$gittan_data_canon"/*', HOOK_BODY)
        self.assertIn("refusing timelog path outside", HOOK_BODY)


class ShellAndPythonNormalizeGittanHomeAlikeTests(unittest.TestCase):
    """The hook's shell half must resolve $GITTAN_HOME the way Python does.

    ``gittan_data_dir()`` strips whitespace and expands a leading ``~``; the hook
    read the raw shell value. The embedded Python resolver *inside the same hook*
    already normalized, so one variable name meant two directories in a single
    run: the worklog went to the expanded path, the scope file to a literal one.

    A literal ``~/dir`` is a **relative** path, so the scope file was simply not
    found — and a missing scope file means "no allowlist", so this failed open
    and logged every repository rather than erroring.

    Rather than assert the shell reimplementation looks right, each case runs the
    hook's own normalization under zsh and compares it to ``gittan_data_dir()``.
    """

    #: Values chosen to cover each normalization rule, not just the happy path.
    CASES = [
        "/tmp/plain-abs",
        "~/gittan-sandbox",         # the case in the review
        "~",
        "  /tmp/padded  ",          # strip(), which the shell did not do
        "/tmp/with space",          # must survive without word-splitting
        "/tmp/with*star",           # must not glob
        "~root/x",                  # ~user, when the user resolves
    ]

    #: Values that are not a usable data directory. Both halves must refuse them
    #: rather than each picking a different directory.
    REJECTED = [
        "data",                     # relative: cwd-dependent, so cwd-divergent
        "./data/nested",
        "../sibling",
        "~nosuchuser42/x",          # ~user that does not resolve: stays relative
    ]

    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("zsh normalization smoke uses macOS path semantics")
        cls.zsh = shutil.which("zsh")
        if not cls.zsh:
            raise unittest.SkipTest("zsh not found")
        # The hook's normalization block, lifted verbatim from the shipped body so
        # the test cannot drift from what actually runs on commit.
        start = HOOK_BODY.index('GITTAN_DATA_DIR="${GITTAN_HOME:-}"')
        end = HOOK_BODY.index('gittan_data_canon=')
        cls.block = textwrap.dedent(HOOK_BODY[start:end])

    def _run_shell(self, gittan_home: str):
        snippet = "set -euo pipefail\n" + self.block + '\nprint -r -- "$GITTAN_DATA_DIR"\n'
        return subprocess.run(
            [self.zsh, "-c", snippet],
            capture_output=True,
            text=True,
            env={**os.environ, "GITTAN_HOME": gittan_home},
        )

    def _shell_value(self, gittan_home: str, *, expect_refusal: bool = False) -> str:
        proc = self._run_shell(gittan_home)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        if expect_refusal:
            return proc.stderr.rstrip("\n")
        return proc.stdout.rstrip("\n")

    def test_shell_matches_gittan_data_dir_for_every_case(self):
        for value in self.CASES:
            with self.subTest(gittan_home=value):
                with mock.patch.dict(os.environ, {"GITTAN_HOME": value}):
                    expected = gittan_data_dir()
                self.assertEqual(self._shell_value(value), str(expected))

    def test_empty_and_whitespace_only_fall_back_to_the_canonical_home(self):
        """``strip()`` makes "   " empty, so it must not become a directory named " "."""
        for value in ("", "   "):
            with self.subTest(gittan_home=repr(value)):
                with mock.patch.dict(os.environ, {"GITTAN_HOME": value}):
                    expected = gittan_data_dir()
                self.assertEqual(expected, Path.home() / ".gittan")
                self.assertEqual(self._shell_value(value), str(expected))

    def test_both_halves_refuse_a_relative_value(self):
        """Neither side may guess. Python raises; the hook warns and stops.

        Anchoring a relative value to some base would keep the two halves in a
        parity race forever (``./x``, ``a/./b``, ``..`` all normalize differently
        in zsh than in PurePath). Refusing collapses the shell's whole obligation
        to one ``== /*`` test, which cannot drift.
        """
        for value in self.REJECTED:
            with self.subTest(gittan_home=value):
                with mock.patch.dict(os.environ, {"GITTAN_HOME": value}):
                    with self.assertRaises(GittanHomeError):
                        gittan_data_dir()
                out = self._shell_value(value, expect_refusal=True)
                self.assertIn("must be an absolute path", out)

    def test_the_hook_exits_cleanly_when_it_refuses(self):
        """A commit must not fail because the data dir is misconfigured.

        The hook is post-commit: the commit already happened. Exiting non-zero
        would print a git error for something the commit had nothing to do with.
        """
        proc = self._run_shell("data")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    def test_an_unresolvable_user_is_refused_rather_than_aborting_zsh(self):
        """zsh aborts on ``${~x}`` for an unknown user; the hook must not.

        It falls through with the value untouched, which is then caught by the
        absolute-path check — a clean refusal instead of a dead shell.
        """
        proc = self._run_shell("~nosuchuser42/x")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("must be an absolute path", proc.stderr)


class CliRefusesAMalformedGittanHomeTests(unittest.TestCase):
    """The refusal must read as a message, not a traceback.

    Typer builds option defaults at *import* time, so the first version of this
    raised before ``main()`` existed and printed a stack trace for a mistyped
    env var. The default is tolerant now and ``main()`` validates explicitly.
    """

    def _run(self, gittan_home: str, *args: str):
        return subprocess.run(
            [sys.executable, "timelog_extract.py", *args],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
            env={**os.environ, "GITTAN_HOME": gittan_home},
        )

    def test_relative_value_exits_two_with_a_readable_error(self):
        proc = self._run("data", "report", "--today", "--screen-time", "off")
        self.assertEqual(proc.returncode, 2, msg=proc.stderr)
        self.assertIn("must be an absolute path", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_the_error_names_the_variable_and_the_offending_value(self):
        proc = self._run("data", "report", "--today")
        self.assertIn("GITTAN_HOME", proc.stderr)
        self.assertIn("data", proc.stderr)

    def test_version_still_works_so_the_user_can_check_their_build(self):
        """``-V`` must not need a valid data dir — it reads nothing."""
        proc = self._run("data", "-V")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("timelog-extract", proc.stdout)


class SetupWritesWhereTheHookReadsTests(unittest.TestCase):
    """``gittan setup`` and the post-commit hook must share one config root.

    These were module-level constants built from ``Path.home()`` at import time,
    so once the hook started reading ``$GITTAN_HOME`` the two sides pointed at
    different directories. The failure is not a silent no-op: the hook treats a
    missing scope file as "no allowlist" and logs **every** repository, so a lost
    allowlist quietly widens what gets written.
    """

    #: Filenames the hook body reads, mapped to the setup helper that writes them.
    SHARED_FILES = {
        "timelog_repos.txt": gittan_scope_file,
        "timelog_filename": gittan_filename_file,
    }

    def test_setup_paths_follow_gittan_home_when_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GITTAN_HOME": tmp}):
                self.assertEqual(gittan_config_dir(), Path(tmp))
                for filename, resolver in self.SHARED_FILES.items():
                    with self.subTest(file=filename):
                        self.assertEqual(resolver(), Path(tmp) / filename)

    def test_setup_paths_use_the_canonical_home_when_unset(self):
        with _no_gittan_home():
            self.assertEqual(gittan_config_dir(), Path.home() / ".gittan")
            for filename, resolver in self.SHARED_FILES.items():
                with self.subTest(file=filename):
                    self.assertEqual(resolver(), Path.home() / ".gittan" / filename)

    def test_setup_paths_are_resolved_per_call_not_frozen_at_import(self):
        """A constant captured at import cannot follow the environment.

        Two different values from the same process is the whole point — that is
        what a module-level ``Path.home() / ".gittan"`` could never do.
        """
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "one", Path(tmp) / "two"
            with mock.patch.dict(os.environ, {"GITTAN_HOME": str(first)}):
                self.assertEqual(gittan_scope_file(), first / "timelog_repos.txt")
            with mock.patch.dict(os.environ, {"GITTAN_HOME": str(second)}):
                self.assertEqual(gittan_scope_file(), second / "timelog_repos.txt")

    def test_the_hook_reads_exactly_the_files_setup_writes(self):
        """Both sides are pinned to the same basenames under the same root.

        Renaming one half without the other reintroduces the divergence, and a
        lost allowlist fails open rather than loudly.
        """
        for filename in self.SHARED_FILES:
            with self.subTest(file=filename):
                self.assertIn(f'"$GITTAN_CFG_DIR/{filename}"', HOOK_BODY)


if __name__ == "__main__":
    unittest.main()
