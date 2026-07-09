"""Tests for Chrome-derived sources: WordPress and Lovable (web)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from chrome_test_support import (
    EPOCH_DELTA_US,
    insert_visit,
    make_chrome_db,
    make_event,
)

from collectors.chrome import (
    collect_chrome,
    is_lovable_web_visit,
    is_wordpress_visit,
)


class ChromeDerivedSourceTests(unittest.TestCase):
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

    def _call(self, profiles, collapse_minutes=0):
        dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        return collect_chrome(
            profiles,
            dt_from,
            dt_to,
            collapse_minutes=collapse_minutes,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            classify_project=lambda text, profs: "Proj",
            make_event=make_event,
        )

    def test_wordpress_admin_title_emits_wordpress_source(self):
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://www.example-news.test/wp-admin/edit.php",
            "Posts ‹ Acme News — WordPress",
            ts,
        )
        profiles = [{"name": "acme-news", "match_terms": ["Acme News", "example-news.test"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "WordPress")
        self.assertIn("Acme News", results[0]["detail"])

    def test_normal_chrome_tab_stays_chrome(self):
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://example.com/docs",
            "Project docs",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["example.com"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Chrome")

    def test_is_wordpress_visit_helper(self):
        self.assertTrue(
            is_wordpress_visit(
                "Dashboard ‹ Acme News — WordPress",
                "https://www.example-news.test/wp-admin/",
            )
        )
        self.assertTrue(
            is_wordpress_visit("Log in", "https://www.example-news.test/wp-admin/"),
        )
        self.assertFalse(is_wordpress_visit("Messenger", "https://www.facebook.com/messages"))
        self.assertFalse(is_wordpress_visit("WordPress.com pricing", "https://wordpress.com/pricing"))

    def test_lovable_web_url_emits_lovable_web_source(self):
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://lovable.dev/projects/d948eea4-83ee-41f7-b8a0-f50e91660950",
            "Demo Project",
            ts,
        )
        profiles = [{"name": "client-alpha", "match_terms": ["demo", "lovable.dev"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Lovable (web)")

    def test_lovableproject_host_emits_lovable_web_source(self):
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://121726c8-b8f3-4a58-8b27-08104baf8fa5.lovableproject.com/",
            "Demo Flow",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["lovableproject", "demo"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Lovable (web)")

    def test_is_lovable_web_visit_helper(self):
        self.assertTrue(is_lovable_web_visit("", "https://lovable.dev/projects/abc"))
        self.assertTrue(
            is_lovable_web_visit(
                "",
                "https://93be36fa-0cb1-4113-9d77-af5a6a1625a0.lovableproject.com/",
            )
        )
        self.assertFalse(is_lovable_web_visit("", "https://example.com/lovable.dev"))
        self.assertFalse(is_lovable_web_visit("Demo", "https://demo.example"))


if __name__ == "__main__":
    unittest.main()
