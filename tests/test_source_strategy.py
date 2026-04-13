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


if __name__ == "__main__":
    unittest.main()
