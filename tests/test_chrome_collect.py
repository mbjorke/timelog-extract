"""Tests for collect_claude_ai_urls, collect_gemini_web_urls, collect_chrome — parameterized LIKE fixes."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.chrome import (
    collect_chrome,
    collect_claude_ai_urls,
    collect_gemini_web_urls,
)

from chrome_test_support import (
    EPOCH_DELTA_US,
    insert_visit,
    make_chrome_db,
    make_event,
)


class CollectClaudeAiUrlsTests(unittest.TestCase):
    """Tests for collect_claude_ai_urls with the parameterized query fix."""

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

    def _call(self, profiles):
        dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        return collect_claude_ai_urls(
            profiles,
            dt_from,
            dt_to,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            uncategorized="Uncategorized",
            make_event=make_event,
        )

    def test_no_claude_urls_in_profiles_returns_empty(self):
        """Profiles with no claude.ai tracked_urls → []."""
        profiles = [{"name": "P", "tracked_urls": ["https://example.com/"]}]
        self.assertEqual(self._call(profiles), [])

    def test_matching_url_returned(self):
        """A visit to a claude.ai URL is collected."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://claude.ai/chat/abc123",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Claude.ai (web)")

    def test_url_with_percent_sign_does_not_error(self):
        """A tracked_url containing % is escaped and does not cause a SQL error."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://claude.ai/chat/50%25encoded",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/chat/50%25encoded"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Claude.ai (web)")

    def test_url_with_underscore_is_escaped(self):
        """A tracked_url containing _ is escaped so it doesn't act as a wildcard."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://claude.ai/project_name/chat",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/project_name"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Claude.ai (web)")

    def test_single_quote_in_url_does_not_error(self):
        """A project URL containing a single-quote is safely parameterized."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://claude.ai/chat/it's-fine",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/chat/it's-fine"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Claude.ai (web)")

    def test_non_matching_url_not_in_results(self):
        """Visits outside the tracked URL list are not returned."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://claude.ai/chat/other",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/chat/specific-id"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 0)


class CollectGeminiWebUrlsTests(unittest.TestCase):
    """Tests for collect_gemini_web_urls with the parameterized query fix."""

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

    def _call(self, profiles):
        dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        return collect_gemini_web_urls(
            profiles,
            dt_from,
            dt_to,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            uncategorized="Uncategorized",
            make_event=make_event,
        )

    def test_no_gemini_urls_returns_empty(self):
        """Profiles with no gemini.google.com tracked_urls → []."""
        profiles = [{"name": "P", "tracked_urls": ["https://example.com/"]}]
        self.assertEqual(self._call(profiles), [])

    def test_matching_gemini_visit_returned(self):
        """A visit to a gemini.google.com URL is collected."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://gemini.google.com/app/abc123",
            "Gemini chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Gemini (web)")

    def test_url_with_percent_sign_does_not_error(self):
        """A tracked_url with % is safely escaped in the LIKE parameter."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://gemini.google.com/app/q%3Dhello",
            "Gemini chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com/app/q%3Dhello"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Gemini (web)")

    def test_single_quote_in_url_does_not_cause_sql_error(self):
        """The old code used chr(39)*2 escaping; now parameterized — must not raise."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://gemini.google.com/app/it's-here",
            "Gemini chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com/app/it's-here"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Gemini (web)")

    def test_underscore_in_tracked_url_is_literal(self):
        """Underscore in a tracked URL is escaped so it matches literally."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://gemini.google.com/app/my_chat",
            "Gemini chat",
            ts,
        )
        insert_visit(
            self.db_path,
            "https://gemini.google.com/app/myXchat",
            "Gemini chat 2",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com/app/my_chat"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertIn("my_chat", results[0]["detail"])


class CollectChromeTests(unittest.TestCase):
    """Tests for collect_chrome with the parameterized query fix."""

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

    def test_no_keywords_returns_empty(self):
        """Profiles with no match_terms or names → []."""
        profiles = [{"name": "", "match_terms": []}]
        self.assertEqual(self._call(profiles), [])

    def test_keyword_matches_url(self):
        """A visit whose URL contains the keyword is returned."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://myproject.io/dashboard",
            "Dashboard",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["myproject"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Chrome")

    def test_keyword_with_percent_sign_does_not_error(self):
        """A keyword containing % is safely escaped and does not raise."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://site.com/100%25complete",
            "Done",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["100%25complete"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Chrome")
        self.assertEqual(results[0]["detail"], "Done")

    def test_keyword_with_underscore_does_not_match_any_char(self):
        """Keyword underscore is escaped; 'foo_bar' doesn't match 'fooXbar'."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://site.com/fooXbar",
            "Decoy",
            ts,
        )
        insert_visit(
            self.db_path,
            "https://site.com/foo_bar",
            "Target",
            ts,
        )
        profiles = [{"name": "ZZZ", "match_terms": ["foo_bar"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["detail"], "Target")

    def test_claude_ai_url_excluded(self):
        """claude.ai visits are excluded even when the keyword matches."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://claude.ai/chat/xyz",
            "Claude",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["claude"]}]
        results = self._call(profiles)
        self.assertEqual(results, [])

    def test_gemini_url_excluded(self):
        """gemini.google.com visits are excluded even when the keyword matches."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://gemini.google.com/app/abc",
            "Gemini",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["gemini"]}]
        results = self._call(profiles)
        self.assertEqual(results, [])

    def test_keyword_with_single_quote_does_not_raise(self):
        """Single-quote in keyword is handled safely by parameterized query."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://site.com/it's-fine",
            "Fine",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["it's-fine"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Chrome")
        self.assertEqual(results[0]["detail"], "Fine")

    def test_multiple_keywords_each_generate_two_params(self):
        """Each keyword produces params for both LOWER(u.url) and LOWER(u.title)."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(self.db_path, "https://alpha.io/", "Alpha Page", ts)
        insert_visit(self.db_path, "https://beta.io/", "Beta Page", ts)
        insert_visit(self.db_path, "https://unrelated.io/", "Nope", ts)

        profiles = [{"name": "Proj", "match_terms": ["alpha", "beta"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 2)

    def test_keyword_matches_title_not_only_url(self):
        """The LIKE clause covers both URL and title; a title-only match is collected."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        insert_visit(
            self.db_path,
            "https://nondescript.io/page",
            "This is my_special project page",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["my_special"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)


class LikeEscapeIntegrationTests(unittest.TestCase):
    """Verify that _like_escape + wildcard wrapping produces correct LIKE params."""

    def test_escaped_percent_param_matches_literal_percent_in_db(self):
        """End-to-end: a URL with a literal % is found only when escaped correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            chrome_dir = (
                home
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / "Default"
            )
            chrome_dir.mkdir(parents=True)
            db_path = chrome_dir / "History"
            make_chrome_db(db_path)

            ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
            insert_visit(db_path, "https://claude.ai/chat/50%done", "Claude", ts)
            insert_visit(db_path, "https://claude.ai/chat/normal", "Claude 2", ts)

            dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
            results = collect_claude_ai_urls(
                [{"name": "Proj", "tracked_urls": ["claude.ai/chat/50%done"]}],
                dt_from,
                dt_to,
                home=home,
                epoch_delta_us=EPOCH_DELTA_US,
                uncategorized="Uncategorized",
                make_event=make_event,
            )
            self.assertEqual(len(results), 1)
            self.assertIn("50%done", results[0]["detail"])

    def test_escaped_underscore_does_not_match_arbitrary_char(self):
        """End-to-end: a keyword with _ only matches the literal underscore character."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            chrome_dir = (
                home
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / "Default"
            )
            chrome_dir.mkdir(parents=True)
            db_path = chrome_dir / "History"
            make_chrome_db(db_path)

            ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
            insert_visit(db_path, "https://example.com/fooXbar", "Decoy", ts)
            insert_visit(db_path, "https://example.com/foo_bar", "Target", ts)

            dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
            results = collect_chrome(
                [{"name": "ZZZ", "match_terms": ["foo_bar"]}],
                dt_from,
                dt_to,
                collapse_minutes=0,
                home=home,
                epoch_delta_us=EPOCH_DELTA_US,
                classify_project=lambda t, p: "ZZZ",
                make_event=make_event,
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["detail"], "Target")


if __name__ == "__main__":
    unittest.main()
