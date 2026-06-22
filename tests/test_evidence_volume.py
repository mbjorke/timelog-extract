"""Tests for the read-only evidence-volume measurement spike (GH-151, slice 1)."""

import unittest

from core.evidence_record import evidence_record_from_event
from core.evidence_volume import (
    build_spike_report,
    measure_evidence_volume,
    project_storage_footprint,
    recommend_engine,
)


def _records(*triples):
    """Build evidence records from (source, ts, detail, project) tuples."""
    return [
        evidence_record_from_event(
            {"source": s, "timestamp": ts, "detail": d, "project": p},
            captured_at="2026-06-18T10:00:00+00:00",
        )
        for (s, ts, d, p) in triples
    ]


class TestMeasureVolume(unittest.TestCase):
    def test_counts_per_source(self):
        records = _records(
            ("Cursor", "2026-06-18T09:00:00+00:00", "a", "Alpha"),
            ("Cursor", "2026-06-18T09:05:00+00:00", "b", "Alpha"),
            ("Chrome", "2026-06-18T09:10:00+00:00", "c", "Alpha"),
        )
        status = {"Cursor": {"events": 2}, "Chrome": {"events": 1}}
        m = measure_evidence_volume(records, status, days_in_range=1)
        self.assertEqual(m["per_source"]["Cursor"]["evidence_records"], 2)
        self.assertEqual(m["per_source"]["Chrome"]["evidence_records"], 1)
        self.assertEqual(m["per_source"]["Cursor"]["source_role"], "direct_work_evidence")
        self.assertEqual(m["totals"]["evidence_records"], 3)

    def test_fingerprint_cardinality_collapses_project_only_dupes(self):
        # Same observation, different project -> one unique fingerprint.
        records = _records(
            ("Cursor", "2026-06-18T09:00:00+00:00", "same", "Alpha"),
            ("Cursor", "2026-06-18T09:00:00+00:00", "same", "Beta"),
        )
        m = measure_evidence_volume(records, {"Cursor": {"events": 2}}, days_in_range=1)
        self.assertEqual(m["totals"]["evidence_records"], 2)
        self.assertEqual(m["totals"]["unique_fingerprints"], 1)

    def test_records_per_day_uses_range(self):
        records = _records(
            ("Cursor", "2026-06-18T09:00:00+00:00", "a", "Alpha"),
            ("Cursor", "2026-06-18T09:05:00+00:00", "b", "Alpha"),
        )
        m = measure_evidence_volume(records, {"Cursor": {"events": 2}}, days_in_range=2)
        self.assertEqual(m["totals"]["records_per_day"], 1.0)

    def test_measures_real_record_bytes(self):
        records = _records(("Cursor", "2026-06-18T09:00:00+00:00", "a", "Alpha"))
        m = measure_evidence_volume(records, {"Cursor": {"events": 1}}, days_in_range=1)
        self.assertGreater(m["totals"]["measured_avg_record_bytes"], 0.0)


class TestFootprintAndRecommendation(unittest.TestCase):
    def _measurement(self, records_per_day, avg_bytes):
        return {
            "totals": {
                "records_per_day": records_per_day,
                "measured_avg_record_bytes": avg_bytes,
            }
        }

    def test_footprint_scales_with_volume(self):
        small = project_storage_footprint(self._measurement(100, 300))
        large = project_storage_footprint(self._measurement(1_000_000, 300))
        self.assertLess(small["daily_jsonl_mb"], large["daily_jsonl_mb"])

    def test_recommend_jsonl_under_threshold(self):
        fp = project_storage_footprint(self._measurement(100, 300))  # ~0.03 MB/day
        rec = recommend_engine(fp, threshold_daily_mb=50.0)
        self.assertEqual(rec["recommended"], "jsonl")

    def test_recommend_tiered_over_threshold(self):
        fp = project_storage_footprint(self._measurement(5_000_000, 300))  # ~1500 MB/day
        rec = recommend_engine(fp, threshold_daily_mb=50.0)
        self.assertEqual(rec["recommended"], "tiered_parquet_duckdb")
        self.assertTrue(rec["caveats"])


class TestBuildSpikeReport(unittest.TestCase):
    def _payload(self):
        return {
            "range": {"from": "2026-06-17T00:00:00+00:00", "to": "2026-06-18T00:00:00+00:00"},
            "collector_status": {"Cursor": {"events": 2}, "Chrome": {"events": 1}},
            "days": {
                "2026-06-18": {
                    "events": [
                        {"source": "Cursor", "timestamp": "2026-06-18T09:00:00+00:00", "detail": "a", "project": "Alpha"},
                        {"source": "Cursor", "timestamp": "2026-06-18T09:05:00+00:00", "detail": "b", "project": "Alpha"},
                        {"source": "Chrome", "timestamp": "2026-06-18T09:10:00+00:00", "detail": "c", "project": "Alpha"},
                    ]
                }
            },
        }

    def test_report_has_recommendation_and_no_io(self):
        report = build_spike_report(self._payload(), captured_at="2026-06-18T10:00:00+00:00")
        self.assertEqual(report["schema"], "timelog_extract.evidence_volume_spike")
        self.assertIn("engine_recommendation", report)
        self.assertIn("recommended", report["engine_recommendation"])
        self.assertEqual(report["totals"]["evidence_records"], 3)
        self.assertEqual(report["measurement_period"]["from"], "2026-06-17T00:00:00+00:00")

    def test_days_in_range_from_payload_span(self):
        report = build_spike_report(self._payload(), captured_at="2026-06-18T10:00:00+00:00")
        # 2026-06-17 .. 2026-06-18 inclusive = 2 days.
        self.assertEqual(report["totals"]["records_per_day"], 1.5)


if __name__ == "__main__":
    unittest.main()
