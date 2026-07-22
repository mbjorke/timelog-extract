"""Tests for the docs privacy guard (#429). Uses a synthetic config only."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import scripts.check_docs_no_client_data as guard

_SYNTH_CONFIG = {
    "projects": [
        {"name": "acme-portal", "customer": "Acme Corp", "project_id": "acme-portal",
         "aliases": ["acmecorp"]},
        {"name": "timelog-extract", "customer": "Blueberry Maybe", "project_id": "timelog-extract"},
    ]
}


class PrivacyGuardTests(unittest.TestCase):
    def _cfg(self, tmp: str) -> Path:
        p = Path(tmp) / "config.json"
        p.write_text(json.dumps(_SYNTH_CONFIG), encoding="utf-8")
        return p

    def test_extracts_client_terms_but_not_self_references(self):
        with TemporaryDirectory() as tmp:
            terms = guard.load_sensitive_terms(self._cfg(tmp))
        lowered = {t.lower() for t in terms}
        self.assertIn("acme corp", lowered)
        self.assertIn("acme-portal", lowered)
        self.assertIn("acmecorp", lowered)
        # Self-references (tool + operator org) are allowlisted, never flagged.
        self.assertNotIn("timelog-extract", lowered)
        self.assertNotIn("blueberry maybe", lowered)

    def test_flags_a_doc_containing_a_client_name(self):
        with TemporaryDirectory() as tmp:
            terms = guard.load_sensitive_terms(self._cfg(tmp))
            doc = Path(tmp) / "leak.md"
            doc.write_text("The Acme Corp portal migration took 3h.\nnothing here.\n", encoding="utf-8")
            hits = guard.scan_file(doc, terms)
        self.assertEqual([h[0] for h in hits], [1])  # line 1 only
        # Matched term is masked in output — never reproduced in full.
        self.assertNotIn("Acme Corp", hits[0][1])

    def test_clean_doc_passes(self):
        with TemporaryDirectory() as tmp:
            terms = guard.load_sensitive_terms(self._cfg(tmp))
            doc = Path(tmp) / "clean.md"
            doc.write_text("A generic client's portal migration took 3h.\n", encoding="utf-8")
            self.assertEqual(guard.scan_file(doc, terms), [])

    def test_word_boundary_avoids_substring_false_positive(self):
        with TemporaryDirectory() as tmp:
            terms = guard.load_sensitive_terms(self._cfg(tmp))
            doc = Path(tmp) / "sub.md"
            # "acmecorp" is a term; "acmecorporation" must not match it.
            doc.write_text("acmecorporation is a different word\n", encoding="utf-8")
            self.assertEqual(guard.scan_file(doc, terms), [])

    def test_no_config_yields_empty_terms(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(guard.load_sensitive_terms(Path(tmp) / "missing.json"), set())


if __name__ == "__main__":
    unittest.main()
