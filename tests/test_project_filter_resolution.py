"""Tests for friendly --project filter resolution."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.report_runtime import build_run_context

RANGE_DAY = "2026-04-01"
RANGE_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
RANGE_END = datetime(2026, 4, 1, tzinfo=timezone.utc)


class ProjectFilterResolutionTests(unittest.TestCase):
    def _ctx(self, *, only_project: str | None, profiles):
        opts = argparse.Namespace(
            today=False,
            yesterday=False,
            last_3_days=False,
            last_week=False,
            last_14_days=False,
            last_month=False,
            worklog=None,
            source_strategy="auto",
            only_project=only_project,
            customer=None,
            project="default-project",
            keywords="",
            email="",
            projects_config="timelog_projects.json",
            date_from=RANGE_DAY,
            date_to=RANGE_DAY,
            include_uncategorized=False,
            source_summary=False,
            quiet=True,
        )
        return build_run_context(
            config_path="timelog_projects.json",
            date_from=RANGE_DAY,
            date_to=RANGE_DAY,
            options=opts,
            local_tz=timezone.utc,
            repo_root=Path(tempfile.gettempdir()),
            as_run_options_fn=lambda o: o,
            get_date_range_fn=lambda _f, _t: (
                RANGE_START,
                RANGE_END,
            ),
            load_profiles_fn=lambda _cfg, _args: (profiles, None, {}),
            resolve_worklog_path_fn=lambda _cli, _cfg, _ws, _root: Path(tempfile.gettempdir()) / "TIMELOG.md",
            want_log_fn=lambda _a: False,
        )

    def test_only_project_unique_partial_match_resolves(self):
        ctx = self._ctx(
            only_project="time",
            profiles=[
                {"name": "Time Log Genius", "aliases": ["tlg"]},
                {"name": "Akturo", "aliases": []},
            ],
        )
        self.assertEqual(ctx.args.only_project, "Time Log Genius")
        self.assertTrue(getattr(ctx.args, "only_project_resolved", False))

    def test_only_project_ambiguous_partial_match_sets_candidates(self):
        ctx = self._ctx(
            only_project="time",
            profiles=[
                {"name": "Time Log Genius", "aliases": []},
                {"name": "timelog-extract", "aliases": []},
            ],
        )
        self.assertEqual(ctx.args.only_project, "time")
        self.assertEqual(
            getattr(ctx.args, "only_project_ambiguous", []),
            ["Time Log Genius", "timelog-extract"],
        )

    def test_only_project_no_match_sets_no_match_flag(self):
        ctx = self._ctx(
            only_project="missing-project",
            profiles=[
                {"name": "Time Log Genius", "aliases": []},
                {"name": "timelog-extract", "aliases": []},
            ],
        )
        self.assertEqual(ctx.args.only_project, "missing-project")
        self.assertTrue(getattr(ctx.args, "only_project_no_match", False))


    def test_only_project_exact_case_insensitive_match(self):
        """An exact case-insensitive name match should resolve immediately."""
        ctx = self._ctx(
            only_project="time log genius",
            profiles=[
                {"name": "Time Log Genius", "aliases": []},
                {"name": "Akturo", "aliases": []},
            ],
        )
        self.assertEqual(ctx.args.only_project, "Time Log Genius")
        # Exact match should NOT set only_project_resolved (only partial sets it)
        self.assertFalse(getattr(ctx.args, "only_project_no_match", False))
        self.assertFalse(getattr(ctx.args, "only_project_ambiguous", None))

    def test_only_project_none_is_no_op(self):
        """Empty/None filter should not modify args."""
        ctx = self._ctx(
            only_project=None,
            profiles=[{"name": "Time Log Genius", "aliases": []}],
        )
        # No crash, no match flags set
        self.assertFalse(getattr(ctx.args, "only_project_no_match", False))
        self.assertFalse(getattr(ctx.args, "only_project_resolved", False))

    def test_only_project_alias_match_resolves(self):
        """Alias match should resolve to canonical project name."""
        ctx = self._ctx(
            only_project="tlg",
            profiles=[
                {"name": "Time Log Genius", "aliases": ["tlg"]},
                {"name": "Akturo", "aliases": ["akt"]},
            ],
        )
        self.assertEqual(ctx.args.only_project, "Time Log Genius")
        self.assertTrue(getattr(ctx.args, "only_project_resolved", False))

    def test_only_project_exact_match_preserves_canonical_casing(self):
        """Exact match should set args.only_project to the canonical profile name casing."""
        ctx = self._ctx(
            only_project="AKTURO",
            profiles=[{"name": "Akturo", "aliases": []}],
        )
        self.assertEqual(ctx.args.only_project, "Akturo")

    def test_only_project_empty_string_is_no_op(self):
        ctx = self._ctx(
            only_project="",
            profiles=[{"name": "Time Log Genius", "aliases": []}],
        )
        self.assertFalse(getattr(ctx.args, "only_project_no_match", False))
        self.assertFalse(getattr(ctx.args, "only_project_resolved", False))


if __name__ == "__main__":
    unittest.main()