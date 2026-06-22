"""Contract tests for the evidence record (GH-151, slice 1)."""

import unittest
from datetime import datetime, timezone

from core.evidence_record import (
    EVIDENCE_SCHEMA_VERSION,
    compute_content_hash,
    compute_evidence_fingerprint,
    evidence_record_from_event,
)


class TestEvidenceFingerprint(unittest.TestCase):
    def test_is_deterministic(self):
        a = compute_evidence_fingerprint("Cursor", "2026-06-18T09:00:00+00:00", "edited foo.py")
        b = compute_evidence_fingerprint("Cursor", "2026-06-18T09:00:00+00:00", "edited foo.py")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)

    def test_varies_with_source(self):
        ts, detail = "2026-06-18T09:00:00+00:00", "edited foo.py"
        self.assertNotEqual(
            compute_evidence_fingerprint("Cursor", ts, detail),
            compute_evidence_fingerprint("Codex IDE", ts, detail),
        )

    def test_varies_with_timestamp(self):
        self.assertNotEqual(
            compute_evidence_fingerprint("Cursor", "2026-06-18T09:00:00+00:00", "x"),
            compute_evidence_fingerprint("Cursor", "2026-06-18T09:01:00+00:00", "x"),
        )

    def test_varies_with_detail(self):
        ts = "2026-06-18T09:00:00+00:00"
        self.assertNotEqual(
            compute_evidence_fingerprint("Cursor", ts, "edited foo.py"),
            compute_evidence_fingerprint("Cursor", ts, "edited bar.py"),
        )

    def test_datetime_and_iso_string_agree(self):
        dt = datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc)
        self.assertEqual(
            compute_evidence_fingerprint("Cursor", dt, "x"),
            compute_evidence_fingerprint("Cursor", dt.isoformat(), "x"),
        )

    def test_z_suffix_matches_plus00(self):
        # RFC-3339 "Z" and "+00:00" must fingerprint identically, or a string
        # from a JSON API would diverge from the equivalent datetime.
        self.assertEqual(
            compute_evidence_fingerprint("Cursor", "2026-06-18T09:00:00Z", "x"),
            compute_evidence_fingerprint("Cursor", "2026-06-18T09:00:00+00:00", "x"),
        )


class TestEvidenceRecord(unittest.TestCase):
    def _event(self, project):
        return {
            "source": "Cursor",
            "timestamp": "2026-06-18T09:00:00+00:00",
            "detail": "edited foo.py",
            "project": project,
        }

    def test_fingerprint_excludes_project(self):
        # Same observation, different classification -> same fingerprint, but the
        # mutable project_at_capture differs. This is the locked anti-corner rule.
        rec_a = evidence_record_from_event(self._event("Alpha"), captured_at="2026-06-18T10:00:00+00:00")
        rec_b = evidence_record_from_event(self._event("Beta"), captured_at="2026-06-18T10:00:00+00:00")
        self.assertEqual(rec_a["fingerprint"], rec_b["fingerprint"])
        self.assertNotEqual(rec_a["project_at_capture"], rec_b["project_at_capture"])

    def test_includes_all_contract_fields(self):
        rec = evidence_record_from_event(self._event("Alpha"), captured_at="2026-06-18T10:00:00+00:00")
        expected = {
            "schema_version",
            "fingerprint",
            "source",
            "source_provenance",
            "observed_at",
            "captured_at",
            "detail",
            "project_at_capture",
            "source_role",
            "prev_hash",
            "content_hash",
        }
        self.assertEqual(set(rec.keys()), expected)
        self.assertEqual(rec["schema_version"], EVIDENCE_SCHEMA_VERSION)
        self.assertEqual(rec["source_role"], "direct_work_evidence")

    def test_content_hash_changes_with_content_not_chain_pointer(self):
        base = evidence_record_from_event(self._event("Alpha"), captured_at="2026-06-18T10:00:00+00:00")
        other_detail = dict(self._event("Alpha"))
        other_detail["detail"] = "edited bar.py"
        changed = evidence_record_from_event(other_detail, captured_at="2026-06-18T10:00:00+00:00")
        self.assertNotEqual(base["content_hash"], changed["content_hash"])
        # prev_hash is excluded from the content hash (chain is verified separately).
        with_prev = evidence_record_from_event(
            self._event("Alpha"), captured_at="2026-06-18T10:00:00+00:00", prev_hash="deadbeef"
        )
        self.assertEqual(base["content_hash"], with_prev["content_hash"])

    def test_content_hash_recomputes(self):
        rec = evidence_record_from_event(self._event("Alpha"), captured_at="2026-06-18T10:00:00+00:00")
        self.assertEqual(rec["content_hash"], compute_content_hash(rec))


if __name__ == "__main__":
    unittest.main()
