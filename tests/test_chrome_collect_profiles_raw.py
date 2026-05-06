from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.chrome import collect_chrome
from chrome_test_support import EPOCH_DELTA_US, insert_visit, make_chrome_db, make_event


class CollectChromeProfilesAndRawTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tmpdir.name)
        chrome_dir = (
            self.home
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Default"
        )
        chrome_dir.mkdir(parents=True)
        self.db_path = chrome_dir / "History"
        make_chrome_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_collects_from_non_default_chrome_profile(self):
        profile_dir = (
            self.home
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Profile 1"
        )
        profile_dir.mkdir(parents=True)
        profile_db = profile_dir / "History"
        make_chrome_db(profile_db)
        ts = datetime(2026, 4, 10, 16, 0, tzinfo=timezone.utc)
        insert_visit(profile_db, "https://myproject.io/from-profile-1", "Profile 1 hit", ts)
        results = collect_chrome(
            [{"name": "Proj", "match_terms": ["myproject"]}],
            datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
            collapse_minutes=0,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            classify_project=lambda text, profs: "Proj",
            make_event=make_event,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["detail"], "Profile 1 hit")

    def test_include_all_returns_non_matching_url_rows(self):
        ts = datetime(2026, 4, 10, 17, 0, tzinfo=timezone.utc)
        insert_visit(self.db_path, "https://example.org/non-project-page", "Random page", ts)
        results = collect_chrome(
            [{"name": "Proj", "match_terms": ["myproject"]}],
            datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
            collapse_minutes=0,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            classify_project=lambda text, profs: "Proj",
            make_event=make_event,
            include_all=True,
        )
        self.assertEqual(len(results), 1)
        self.assertIn("example.org/non-project-page", results[0]["detail"])

    def test_include_all_can_filter_by_url_substring(self):
        ts = datetime(2026, 4, 10, 18, 0, tzinfo=timezone.utc)
        insert_visit(self.db_path, "https://example.org/alpha", "Alpha", ts)
        insert_visit(self.db_path, "https://example.org/beta", "Beta", ts)
        results = collect_chrome(
            [{"name": "Proj", "match_terms": ["none"]}],
            datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
            collapse_minutes=0,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            classify_project=lambda text, profs: "Proj",
            make_event=make_event,
            include_all=True,
            contains_url="alpha",
        )
        self.assertEqual(len(results), 1)
        self.assertIn("example.org/alpha", results[0]["detail"])


if __name__ == "__main__":
    unittest.main()

