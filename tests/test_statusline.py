"""Tests for the gittan statusline (S1 — unconfigured-project warning)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

from core.config import normalize_profile

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gittan_statusline.py"
_spec = importlib.util.spec_from_file_location("gittan_statusline", _SCRIPT)
sl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sl)


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


class MainSmokeTests(unittest.TestCase):
    def test_main_never_raises(self):
        # The statusline must never disrupt the prompt; main returns 0 regardless.
        # Capture stdout so the printed line doesn't pollute test output.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sl.main(), 0)


if __name__ == "__main__":
    unittest.main()
