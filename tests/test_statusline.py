"""Tests for the gittan statusline (S1 warning + S2 unreported nudge)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from core.config import normalize_profile
from core.reported_time import ReportedTimeRecord, append_record

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gittan_statusline.py"
_spec = importlib.util.spec_from_file_location("gittan_statusline", _SCRIPT)
sl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sl)

_MOCK_CWD = "/fixture/statusline-cwd"


def _profiles():
    return [normalize_profile({"name": "Timelog", "match_terms": ["timelog-extract"]})]


class ProjectStatusTests(unittest.TestCase):
    def test_no_slug_is_quiet(self):
        # Outside a git repo we must not warn spuriously.
        self.assertEqual(sl.project_status("", _profiles()), "")

    def test_matched_project_is_confirmed(self):
        self.assertEqual(
            sl.project_status("mbjorke/timelog-extract", _profiles()),
            "gittan: Timelog",
        )

    def test_unconfigured_project_warns(self):
        self.assertEqual(sl.project_status("acme/secret-thing", _profiles()), sl.WARNING)

    def test_no_profiles_warns(self):
        # A git repo but an empty/absent config -> nudge to set up.
        self.assertEqual(sl.project_status("acme/anything", []), sl.WARNING)


class UnreportedTests(unittest.TestCase):
    """S2 - unreported = observed - handled for today's current project."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.day = "2026-06-20"

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_observed(self, project, hours, captured=None):
        captured = captured or self.day  # default: cache refreshed today (fresh)
        base = self.home / ".gittan" / "observed"
        base.mkdir(parents=True, exist_ok=True)
        # Local-tz noon so astimezone().date() stays on `captured` in any timezone
        # (a midnight-UTC stamp would slip to the previous day west of UTC).
        captured_at = datetime.fromisoformat(f"{captured}T12:00:00").astimezone().isoformat()
        row = {"project": project, "date": self.day, "hours": hours, "captured_at": captured_at}
        (base / f"{self.day[:7]}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    def _seed_reported(self, project, hours, state="confirmed"):
        append_record(
            ReportedTimeRecord(
                date=self.day, project=project, hours=hours, source="session",
                state=state, origin_ref=[f"{self.day}T0900"],
            ),
            home=self.home,
        )

    def test_unreported_is_observed_minus_handled(self):
        self._seed_observed("Alpha", 5.0)
        self._seed_reported("Alpha", 2.0, "confirmed")
        self.assertEqual(sl.unreported_hours("Alpha", self.day, self.home), 3.0)

    def test_dismissed_counts_as_handled(self):
        self._seed_observed("Alpha", 4.0)
        self._seed_reported("Alpha", 4.0, "dismissed")
        self.assertEqual(sl.unreported_hours("Alpha", self.day, self.home), 0.0)

    def test_statusline_shows_unreported_for_current_project(self):
        # slug "acme/alpha" classifies to profile "Alpha"; 5h observed, 1h handled.
        profiles = [normalize_profile({"name": "Alpha", "match_terms": ["alpha"]})]
        self._seed_observed("Alpha", 5.0)
        self._seed_reported("Alpha", 1.0, "confirmed")
        line = sl.statusline_text("acme/alpha", profiles, self.day, self.home)
        self.assertEqual(line, "gittan: Alpha · ⏱ 4.0h unreported · gittan reported")

    def test_statusline_all_reported(self):
        profiles = [normalize_profile({"name": "Alpha", "match_terms": ["alpha"]})]
        self._seed_observed("Alpha", 3.0)
        self._seed_reported("Alpha", 3.0, "confirmed")
        line = sl.statusline_text("acme/alpha", profiles, self.day, self.home)
        self.assertEqual(line, "gittan: Alpha · ✓ all reported today")

    def test_statusline_sub_tenth_hour_unreported_shows_all_clear(self):
        profiles = [normalize_profile({"name": "Alpha", "match_terms": ["alpha"]})]
        self._seed_observed("Alpha", 3.04)
        self._seed_reported("Alpha", 3.0, "confirmed")
        line = sl.statusline_text("acme/alpha", profiles, self.day, self.home)
        self.assertEqual(line, "gittan: Alpha · ✓ all reported today")
        self.assertNotIn("0.0h unreported", line)

    def test_statusline_stale_cache_nudges_report(self):
        # Cache last refreshed yesterday: never claim all-clear, even if fully handled.
        profiles = [normalize_profile({"name": "Alpha", "match_terms": ["alpha"]})]
        self._seed_observed("Alpha", 5.0, captured="2026-06-19")
        self._seed_reported("Alpha", 5.0, "confirmed")
        line = sl.statusline_text("acme/alpha", profiles, self.day, self.home)
        self.assertEqual(line, "gittan: Alpha · ⟳ gittan report")

    def test_statusline_no_cache_nudges_report(self):
        # No observed cache at all -> stale nudge, not a false all-clear.
        profiles = [normalize_profile({"name": "Alpha", "match_terms": ["alpha"]})]
        line = sl.statusline_text("acme/alpha", profiles, self.day, self.home)
        self.assertEqual(line, "gittan: Alpha · ⟳ gittan report")

    def test_statusline_unconfigured_has_no_number(self):
        line = sl.statusline_text("acme/secret", [normalize_profile({"name": "Alpha", "match_terms": ["alpha"]})], self.day, self.home)
        self.assertEqual(line, sl.WARNING)

    def test_statusline_no_slug_is_blank(self):
        self.assertEqual(sl.statusline_text("", _profiles(), self.day, self.home), "")


class MainSmokeTests(unittest.TestCase):
    def test_main_never_raises(self):
        # Exercise main()'s wiring without live git/config/jsonl I/O (that path is
        # covered by the pure helpers above and can take 30s+ against ~/.gittan).
        with contextlib.redirect_stdout(io.StringIO()), patch.object(
            sl, "_resolve_cwd", return_value=_MOCK_CWD
        ), patch("core.repo_slug.resolve_path_repo_slug", return_value=""), patch.object(
            sl, "_load_profiles", return_value=[]
        ):
            self.assertEqual(sl.main(), 0)

    def test_main_swallows_errors(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), patch.object(
            sl, "_resolve_cwd", side_effect=RuntimeError("boom")
        ):
            self.assertEqual(sl.main(), 0)
        self.assertEqual(buf.getvalue(), "\n")


if __name__ == "__main__":
    unittest.main()
