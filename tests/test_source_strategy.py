"""Tests for source-strategy runtime resolution."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.report_runtime import build_run_context


class SourceStrategyTests(unittest.TestCase):
    def _options(
        self,
        strategy: str,
        worklog: str | None = None,
        attribution_mode: str | None = None,
        github_user: str | None = None,
    ):
        return argparse.Namespace(
            today=False,
            yesterday=False,
            last_3_days=False,
            last_week=False,
            last_14_days=False,
            last_month=False,
            worklog=worklog,
            source_strategy=strategy,
            attribution_mode=attribution_mode,
            github_user=github_user,
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
            self.assertEqual(ctx.source_strategy_effective, "per-project")
            self.assertEqual(ctx.args.primary_source, "per-project")

    def test_per_project_mode_with_two_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            cfg = repo / "timelog_projects.json"
            log_a = repo / "client-a.md"
            log_b = repo / "client-b.md"
            log_a.write_text("# a\n", encoding="utf-8")
            log_b.write_text("# b\n", encoding="utf-8")

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
                    [
                        {"name": "client-a", "worklog": str(log_a)},
                        {"name": "client-b", "worklog": str(log_b)},
                    ],
                    cfg,
                    {},
                ),
                resolve_worklog_path_fn=lambda _cli, _cfg, _ws, _root: repo / "TIMELOG.md",
                want_log_fn=lambda _a: False,
            )
            self.assertEqual(ctx.source_strategy_effective, "per-project")
            self.assertEqual(ctx.args.primary_source, "per-project")
            self.assertEqual(len(ctx.worklog_paths), 2)

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

    def test_commit_first_injects_empty_worklog_and_disables_project_worklogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            project_log = repo / "client-a" / "TIMELOG.md"
            project_log.parent.mkdir(parents=True, exist_ok=True)
            project_log.write_text("# client-a\n", encoding="utf-8")

            ctx = build_run_context(
                config_path="timelog_projects.json",
                date_from="2026-04-01",
                date_to="2026-04-01",
                options=self._options("auto", None, attribution_mode="commit-first"),
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

            injected = Path(ctx.worklog_paths[0]) if ctx.worklog_paths else None
            try:
                self.assertEqual(ctx.args.github_source, "on")
                self.assertEqual(ctx.args.mail_source, "off")
                self.assertEqual(ctx.args.chrome_source, "off")
                self.assertEqual(ctx.args.screen_time, "off")
                self.assertEqual(ctx.args.source_strategy, "balanced")

                # Commit-first mode injects an explicit empty worklog and disables per-project worklogs.
                self.assertEqual(len(ctx.worklog_paths), 1)
                self.assertTrue(injected.exists())
                self.assertTrue(injected.is_file())
                self.assertEqual(injected.stat().st_size, 0)
                self.assertNotEqual(injected.resolve(), project_log.resolve())
            finally:
                if injected is not None and injected.exists():
                    injected.unlink(missing_ok=True)

    def test_commit_first_preserves_multi_user_github_logins(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = build_run_context(
                config_path="timelog_projects.json",
                date_from="2026-04-01",
                date_to="2026-04-01",
                options=self._options("auto", None, attribution_mode="commit-first", github_user="user-a,user-b"),
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
            injected_path = Path(ctx.worklog_paths[0]) if ctx.worklog_paths else None
            try:
                self.assertEqual(ctx.args.github_source, "on")
                self.assertEqual(ctx.args.github_user, "user-a,user-b")
            finally:
                if injected_path is not None and injected_path.exists():
                    injected_path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
