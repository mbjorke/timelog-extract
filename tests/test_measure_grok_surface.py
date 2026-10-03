"""Tests for the Grok local-surface measurement.

The point of the script is to answer one question — does the Project name reach
the URL or the title — so the tests fabricate the three answers it must be able
to tell apart, plus the two null results that must not be confused.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "measure_grok_surface.py"
_spec = importlib.util.spec_from_file_location("measure_grok_surface", _SCRIPT)
mgs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mgs)

_EPOCH = 11_644_473_600_000_000


def _visit(url, title, day=1):
    stamp = datetime(2026, 8, day, 12, 0, tzinfo=timezone.utc)
    return (int(stamp.timestamp() * 1_000_000) + _EPOCH, url, title)


class PathShapeTests(unittest.TestCase):
    def test_opaque_ids_collapse_to_a_template(self):
        shape, cid = mgs.path_shape("https://grok.com/c/0f7a1c2e-1111-4222-8333-abcdef012345")
        self.assertEqual(shape, "grok.com/c/<id>")
        self.assertEqual(cid, "0f7a1c2e-1111-4222-8333-abcdef012345")

    def test_route_names_survive_templating(self):
        shape, cid = mgs.path_shape("https://grok.com/project/Gxk29dhslw02Nfk1/chat")
        self.assertEqual(shape, "grok.com/project/<id>/chat")
        # The only id here is the project's, and no chat id follows a
        # conversation route, so this URL names no conversation.
        self.assertIsNone(cid)

    def test_an_unknown_path_segment_is_redacted_not_kept(self):
        """A short segment no id pattern matches is where a customer name sits."""
        shape, cid = mgs.path_shape("https://grok.com/project/Acme/c/aaaaaaaaaaaaaaaaaa")
        self.assertEqual(shape, "grok.com/project/<seg>/c/<id>")
        self.assertNotIn("Acme", shape)
        self.assertEqual(cid, "aaaaaaaaaaaaaaaaaa")

    def test_conversation_id_comes_from_the_chat_route_not_the_project(self):
        """Two chats in one project are two conversations, not one retitled thread."""
        rows = [
            _visit("https://grok.com/project/Gxk29dhslw02Nfk1/c/aaaaaaaaaaaaaaaaaa", "Defensible Hours"),
            _visit("https://grok.com/project/Gxk29dhslw02Nfk1/c/bbbbbbbbbbbbbbbbbb", "Ledger model"),
        ]
        self.assertEqual(mgs.analyse(rows)["conversations"], 2)

    def test_only_the_parsed_host_counts_as_grok(self):
        for url in (
            "https://grok.com/c/abc",
            "https://grok.com/",
            "https://x.com/i/grok",
            "https://x.com/i/grok/whatever",
        ):
            self.assertTrue(mgs.is_grok_url(url), url)
        for url in (
            "https://notgrok.com.example/c/abc",
            "https://example.com/?redirect=grok.com/c/abc",
            "https://grok.com.evil.test/c/abc",
            "https://x.com/home",
        ):
            self.assertFalse(mgs.is_grok_url(url), url)

    def test_bare_host_has_no_conversation_id(self):
        self.assertEqual(mgs.path_shape("https://grok.com/"), ("grok.com", None))


class Q1Tests(unittest.TestCase):
    def test_a_project_route_in_the_url_is_the_strongest_answer(self):
        rows = [
            _visit("https://grok.com/project/Gxk29dhslw02Nfk1/c/aaaaaaaaaaaaaaaaaa", "Defensible Hours"),
            _visit("https://grok.com/project/Gxk29dhslw02Nfk1/c/bbbbbbbbbbbbbbbbbb", "Ledger model"),
        ]
        report = mgs.analyse(rows)
        report.update(browsers_seen=["Chrome"], browsers_with_hits=["Chrome"], app_dirs=[])
        self.assertIn("URL CARRIES A PROJECT ROUTE", mgs.verdict(report))

    def test_a_title_segment_shared_by_some_conversations_is_project_like(self):
        rows = [
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "Gittan — Defensible Hours"),
            _visit("https://grok.com/c/bbbbbbbbbbbbbbbbbb", "Gittan — Ledger model"),
            _visit("https://grok.com/c/cccccccccccccccccc", "Holiday plans"),
        ]
        report = mgs.analyse(rows)
        segments = dict(report["project_like_title_segments"])
        self.assertEqual(segments.get("Gittan"), 2)
        report.update(browsers_seen=["Chrome"], browsers_with_hits=["Chrome"], app_dirs=[])
        self.assertIn("TITLE MAY CARRY THE PROJECT", mgs.verdict(report))

    def test_a_thin_sample_sharing_one_segment_is_ambiguous_not_negative(self):
        """Two chats both labelled the same could be branding or one project."""
        rows = [
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "Defensible Hours | Grok"),
            _visit("https://grok.com/c/bbbbbbbbbbbbbbbbbb", "Ledger model | Grok"),
        ]
        report = mgs.analyse(rows)
        self.assertEqual(report["project_like_title_segments"], [])
        self.assertIn("Grok", report["constant_title_segments"])
        report.update(browsers_seen=["Chrome"], browsers_with_hits=["Chrome"], app_dirs=[])
        self.assertIn("AMBIGUOUS", mgs.verdict(report))

    def test_a_segment_on_every_one_of_many_conversations_reads_as_branding(self):
        rows = [
            _visit(f"https://grok.com/c/{letter * 18}", f"Thread {i} | Grok")
            for i, letter in enumerate("abcdef")
        ]
        report = mgs.analyse(rows)
        self.assertEqual(report["conversations"], 6)
        self.assertIn("Grok", report["constant_title_segments"])
        report.update(browsers_seen=["Chrome"], browsers_with_hits=["Chrome"], app_dirs=[])
        self.assertIn("PROJECT NOT OBSERVABLE", mgs.verdict(report))

    def test_renames_are_not_claimed_to_be_measurable(self):
        """Chromium keeps the title on the URL row, so a rename leaves no trace.

        The earlier version of this script counted threads "seen under more than
        one title" and called it evidence for Q2. The query joins each visit to
        ``urls.title``, so every visit to one URL reports that URL's *current*
        title — the metric could only ever have fired if the URL changed too, and
        the fixture that proved it fed per-visit titles the real query cannot
        return.
        """
        rows = [
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "Defensible Hours", day=1),
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "Defensible Hours", day=2),
        ]
        report = mgs.analyse(rows)
        self.assertEqual(report["conversations"], 1)
        self.assertNotIn("conversations_seen_under_more_than_one_title", report)
        report.update(browsers_seen=["Chrome"], browsers_with_hits=["Chrome"], app_dirs=[])
        report["verdict"] = mgs.verdict(report)
        self.assertIn("not measurable here", mgs.render(report))


class NullResultTests(unittest.TestCase):
    """An unreadable browser and an empty history are different answers."""

    def test_no_readable_browser_is_inconclusive_not_a_negative(self):
        report = mgs.analyse([])
        report.update(browsers_seen=[], browsers_with_hits=[], app_dirs=[])
        self.assertIn("INCONCLUSIVE", mgs.verdict(report))

    def test_readable_browser_with_no_grok_visits_says_so(self):
        report = mgs.analyse([])
        report.update(browsers_seen=["Chrome", "Brave"], browsers_with_hits=[], app_dirs=[])
        self.assertIn("NO DATA", mgs.verdict(report))


class NullResultBoundaryTests(unittest.TestCase):
    """The cases a thin or unreadable sample must not be turned into a negative."""

    def test_an_unreadable_profile_is_inconclusive_not_no_data(self):
        """query_chrome returns [] for a copy or SQL failure as well as for no rows."""
        report = mgs.analyse([])
        report.update(browsers_seen=[], browsers_with_hits=[], app_dirs=[], browsers_unreadable=["Chrome"])
        said = mgs.verdict(report)
        self.assertIn("INCONCLUSIVE", said)
        self.assertNotIn("NO DATA", said)

    def test_profile_readable_rejects_a_file_that_is_not_a_history_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
            handle.write(b"not a sqlite database")
            path = Path(handle.name)
        try:
            self.assertFalse(mgs.profile_readable(path))
        finally:
            path.unlink()

    def test_few_titles_and_no_shared_segment_is_insufficient_not_negative(self):
        """Greptile's case: a couple of visits whose titles are all distinct."""
        rows = [
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "Defensible Hours"),
            _visit("https://grok.com/c/bbbbbbbbbbbbbbbbbb", "Holiday plans"),
        ]
        report = mgs.analyse(rows)
        self.assertEqual(report["titled_conversations"], 2)
        report.update(browsers_seen=["Chrome"], browsers_with_hits=["Chrome"], app_dirs=[])
        said = mgs.verdict(report)
        self.assertIn("INSUFFICIENT TITLES", said)
        self.assertNotIn("PROJECT NOT OBSERVABLE", said)


class PrivacyTests(unittest.TestCase):
    def test_the_default_report_never_prints_a_url_or_a_conversation_id(self):
        rows = [
            _visit("https://grok.com/c/secretid0123456789", "Acme Corp — merger terms"),
            _visit("https://grok.com/c/otherid09876543210", "Acme Corp — pricing"),
        ]
        report = mgs.analyse(rows)
        report.update(browsers_seen=["Chrome"], browsers_with_hits=["Chrome"], app_dirs=[])
        report["verdict"] = mgs.verdict(report)
        rendered = mgs.render(report)
        self.assertNotIn("secretid0123456789", rendered)
        self.assertNotIn("merger terms", rendered)
        self.assertNotIn("Acme Corp", rendered)
        # The structural fact still survives the redaction.
        self.assertIn("segment(s)", rendered)
        self.assertIn("9 chars", rendered)

    def test_json_strips_segment_text_unless_samples_are_requested(self):
        rows = [
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "Acme Corp — merger terms"),
            _visit("https://grok.com/c/bbbbbbbbbbbbbbbbbb", "Acme Corp — pricing"),
            _visit("https://grok.com/c/cccccccccccccccccc", "Holiday plans"),
        ]
        report = mgs.analyse(rows)
        redacted = mgs._json_payload(report, show_samples=0)
        self.assertNotIn("Acme Corp", json.dumps(redacted))
        self.assertTrue(redacted["segments_redacted"])
        self.assertEqual(redacted["project_like_title_segments"], [[9, 2]])
        # Opt-in returns the text unchanged.
        self.assertIn("Acme Corp", json.dumps(mgs._json_payload(report, show_samples=3)))

    def test_json_honours_the_sample_limit_rather_than_returning_everything(self):
        rows = [
            _visit(f"https://grok.com/c/{letter * 18}", f"Client {i} — work")
            for i, letter in enumerate("abcdef")
        ] + [
            _visit(f"https://grok.com/c/{letter * 17}z", f"Client {i} — more")
            for i, letter in enumerate("abcdef")
        ]
        report = mgs.analyse(rows)
        self.assertGreater(len(report["project_like_title_segments"]), 1)
        payload = mgs._json_payload(report, show_samples=1)
        self.assertEqual(len(payload["project_like_title_segments"]), 1)
        self.assertTrue(payload["contains_samples"])

    def test_a_discovered_directory_name_never_reaches_the_report(self):
        """`grok-Acme` under Application Support must not print as itself."""
        report = mgs.analyse([])
        report.update(
            browsers_seen=["Chrome"],
            browsers_with_hits=[],
            app_dirs=[{"library": "Application Support", "hint": "grok", "is_dir": True}],
        )
        report["verdict"] = mgs.verdict(report)
        rendered = mgs.render(report)
        self.assertIn("matching 'grok'", rendered)
        self.assertIn("Application Support", rendered)
        self.assertNotIn("Acme", rendered)


if __name__ == "__main__":
    unittest.main()
