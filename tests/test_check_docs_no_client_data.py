"""Tests for the docs privacy guard (#429). Uses a synthetic config only."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

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

    def test_absent_config_skips_but_broken_config_fails_closed(self):
        with TemporaryDirectory() as tmp:
            # Genuinely absent → empty set (caller skips; e.g. CI).
            self.assertEqual(guard.load_sensitive_terms(Path(tmp) / "missing.json"), set())
            # Present but unparseable → ConfigError (caller must fail closed).
            broken = Path(tmp) / "broken.json"
            broken.write_text("{ not valid json", encoding="utf-8")
            with self.assertRaises(guard.ConfigError):
                guard.load_sensitive_terms(broken)

    def test_malformed_projects_shape_raises_config_error(self):
        with TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.json"
            cfg.write_text(json.dumps({"projects": {}}), encoding="utf-8")
            with self.assertRaises(guard.ConfigError):
                guard.load_sensitive_terms(cfg)

    def test_main_fails_closed_on_broken_config(self):
        with TemporaryDirectory() as tmp:
            broken = Path(tmp) / "config.json"
            broken.write_text("{ broken", encoding="utf-8")
            doc = Path(tmp) / "doc.md"
            doc.write_text("anything\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GITTAN_PROJECTS_CONFIG": str(broken)}):
                rc = guard.main([str(doc)])
            self.assertEqual(rc, 1)

    def test_main_fails_closed_on_malformed_config_shape(self):
        with TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.json"
            cfg.write_text(json.dumps({"projects": {}}), encoding="utf-8")
            doc = Path(tmp) / "doc.md"
            doc.write_text("anything\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GITTAN_PROJECTS_CONFIG": str(cfg)}):
                rc = guard.main([str(doc)])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
