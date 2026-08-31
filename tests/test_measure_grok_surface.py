"""Tests for the Grok local-surface measurement.

The point of the script is to answer one question — does the Project name reach
the URL or the title — so the tests fabricate the three answers it must be able
to tell apart, plus the two null results that must not be confused.
"""

from __future__ import annotations

import importlib.util
import json
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
        self.assertEqual(cid, "Gxk29dhslw02Nfk1")

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

    def test_a_retitled_thread_is_counted_because_it_breaks_title_bindings(self):
        rows = [
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "New conversation", day=1),
            _visit("https://grok.com/c/aaaaaaaaaaaaaaaaaa", "Defensible Hours", day=2),
        ]
        report = mgs.analyse(rows)
        self.assertEqual(report["conversations"], 1)
        self.assertEqual(report["conversations_seen_under_more_than_one_title"], 1)


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


if __name__ == "__main__":
    unittest.main()
