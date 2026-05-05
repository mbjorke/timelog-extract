"""Tests for source-strategy runtime resolution."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.report_runtime import build_run_context


class SourceStrategyTests(unittest.TestCase):
    def _options(self, strategy: str, worklog: str | None = None):
        return argparse.Namespace(
            today=False,
            yesterday=False,
            last_3_days=False,
            last_week=False,
            last_14_days=False,
            last_month=False,
            worklog=worklog,
            source_strategy=strategy,
            only_project=None,
            customer=None,
            project="default-project",
            keywords="",
            email="",
            projects_config="timelog_projects.json",
            date_from="2026-04-01",
            date_to="2026-04-01",
            include_uncategorized=False,
            source_summary=False,
            quiet=True,
        )

    def test_auto_uses_worklog_first_when_worklog_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            wl = repo / "TIMELOG.md"
            wl.write_text("# TIMELOG\n", encoding="utf-8")

            ctx = build_run_context(
                config_path="timelog_projects.json",
                date_from="2026-04-01",
                date_to="2026-04-01",
                options=self._options("auto", str(wl)),
                local_tz=timezone.utc,
                repo_root=repo,
                as_run_options_fn=lambda o: o,
                get_date_range_fn=lambda _f, _t: (
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                ),
                load_profiles_fn=lambda _cfg, _args: ([{"name": "default-project"}], None, {}),
                resolve_worklog_path_fn=lambda cli, _cfg, _ws, _root: Path(cli),
                want_log_fn=lambda _a: False,
            )
            self.assertEqual(ctx.source_strategy_effective, "worklog-first")

    def test_worklog_first_falls_back_when_worklog_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            wl = repo / "TIMELOG.md"

            ctx = build_run_context(
                config_path="timelog_projects.json",
                date_from="2026-04-01",
                date_to="2026-04-01",
                options=self._options("worklog-first", str(wl)),
                local_tz=timezone.utc,
                repo_root=repo,
                as_run_options_fn=lambda o: o,
                get_date_range_fn=lambda _f, _t: (
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                ),
                load_profiles_fn=lambda _cfg, _args: ([{"name": "default-project"}], None, {}),
                resolve_worklog_path_fn=lambda cli, _cfg, _ws, _root: Path(cli),
                want_log_fn=lambda _a: False,
            )
            self.assertEqual(ctx.source_strategy_effective, "balanced")

    def test_context_collects_per_project_worklog_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            central = repo / "TIMELOG.md"
            central.write_text("# central\n", encoding="utf-8")
            project_log = repo / "client-a" / "TIMELOG.md"
            project_log.parent.mkdir(parents=True, exist_ok=True)
            project_log.write_text("# client-a\n", encoding="utf-8")

            ctx = build_run_context(
                config_path="timelog_projects.json",
                date_from="2026-04-01",
                date_to="2026-04-01",
                options=self._options("auto", None),
                local_tz=timezone.utc,
                repo_root=repo,
                as_run_options_fn=lambda o: o,
                get_date_range_fn=lambda _f, _t: (
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                ),
                load_profiles_fn=lambda _cfg, _args: (
                    [{"name": "client-a", "worklog": "client-a/TIMELOG.md"}],
                    repo / "timelog_projects.json",
                    {},
                ),
                resolve_worklog_path_fn=lambda _cli, _cfg, _ws, _root: central,
                want_log_fn=lambda _a: False,
            )
            self.assertEqual(ctx.worklog_path, project_log.resolve())
            self.assertEqual(ctx.worklog_paths, [project_log.resolve()])

    def test_explicit_worklog_flag_keeps_single_worklog_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            override = repo / "override.md"
            override.write_text("# override\n", encoding="utf-8")

            ctx = build_run_context(
                config_path="timelog_projects.json",
                date_from="2026-04-01",
                date_to="2026-04-01",
                options=self._options("auto", str(override)),
                local_tz=timezone.utc,
                repo_root=repo,
                as_run_options_fn=lambda o: o,
                get_date_range_fn=lambda _f, _t: (
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                ),
                load_profiles_fn=lambda _cfg, _args: (
                    [{"name": "client-a", "worklog": "client-a/TIMELOG.md"}],
                    repo / "timelog_projects.json",
                    {},
                ),
                resolve_worklog_path_fn=lambda cli, _cfg, _ws, _root: Path(cli),
                want_log_fn=lambda _a: False,
            )
            self.assertEqual(ctx.worklog_paths, [override])

    def test_top_level_worklog_keeps_base_plus_per_project_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            central = repo / "workspace.md"
            central.write_text("# workspace\n", encoding="utf-8")
            project_log = repo / "client-a" / "TIMELOG.md"
            project_log.parent.mkdir(parents=True, exist_ok=True)
            project_log.write_text("# client-a\n", encoding="utf-8")

            ctx = build_run_context(
                config_path="timelog_projects.json",
                date_from="2026-04-01",
                date_to="2026-04-01",
                options=self._options("auto", None),
                local_tz=timezone.utc,
                repo_root=repo,
                as_run_options_fn=lambda o: o,
                get_date_range_fn=lambda _f, _t: (
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                    datetime(2026, 4, 1, tzinfo=timezone.utc),
                ),
                load_profiles_fn=lambda _cfg, _args: (
                    [{"name": "client-a", "worklog": "client-a/TIMELOG.md"}],
                    repo / "timelog_projects.json",
                    {"worklog": str(central)},
                ),
                resolve_worklog_path_fn=lambda _cli, _cfg, _ws, _root: central,
                want_log_fn=lambda _a: False,
            )
            self.assertEqual(ctx.worklog_path, central)
            self.assertEqual(ctx.worklog_paths, [central, project_log.resolve()])

if __name__ == "__main__":
    unittest.main()
