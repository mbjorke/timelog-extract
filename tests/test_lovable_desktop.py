"""Tests for Lovable Desktop (Electron) history discovery."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from collectors.lovable_desktop import (
    _extract_lovable_urls,
    _filter_lovable_storage_urls,
    _merge_storage_events,
    _pick_storage_urls_from_blob,
    _trim_lovable_url_blob_suffix,
    collect_lovable_desktop,
    lovable_desktop_history_candidates,
    lovable_desktop_root,
)


class LovableDesktopTests(unittest.TestCase):
    def test_root_path(self):
        home = Path("/Users/example")
        self.assertEqual(
            lovable_desktop_root(home),
            home / "Library" / "Application Support" / "lovable-desktop",
        )

    def test_candidates_empty_when_missing(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(lovable_desktop_history_candidates(home), [])

    def test_candidates_finds_nonempty_history_files(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            hist = home / "Library/Application Support/lovable-desktop/Default/History"
            hist.parent.mkdir(parents=True)
            hist.write_bytes(b"\x00" * 4096)
            paths = lovable_desktop_history_candidates(home)
            self.assertEqual(len(paths), 1)
            self.assertEqual(paths[0].resolve(), hist.resolve())

    def test_candidates_skips_zero_byte_files(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            hist = home / "Library/Application Support/lovable-desktop/Default/History"
            hist.parent.mkdir(parents=True)
            hist.write_bytes(b"")
            self.assertEqual(lovable_desktop_history_candidates(home), [])

    def test_extract_lovable_urls_from_blob(self):
        blob = (
            b"prefix https://lovable.dev/foo bar "
            b"https://id-preview--abc.lovable.app/path?q=1 "
            b"https://x.lovableproject.com/hello "
            b"https://id-preview--uuid.lov "
            b"https://uuid.lovableproject. suffix"
        )
        urls = _extract_lovable_urls(blob)
        self.assertIn("https://lovable.dev/foo", urls)
        self.assertTrue(any("lovable.app/path" in u for u in urls))
        self.assertTrue(any("lovableproject.com/hello" in u for u in urls))
        self.assertNotIn("https://id-preview--uuid.lov", urls)
        self.assertIn("https://uuid.lovableproject.", urls)

    def test_filter_lovable_storage_urls_strict_drops_invalid_host_variants(self):
        urls = [
            "https://lovable.dev",
            "https://lovable.dev/",
            "https://www.lovable.dev",
            "https://www.lovable.dev/",
            "https://lovable.dev/projects/abc",
            "https://id-preview--abc.lovable.app/path",
            "https://x.lovableproject.com/hello",
            "https://lovable.devyO",
            "https://lovable.dev116cS",
            "https://lovable.dev4:e",
        ]
        filtered = _filter_lovable_storage_urls(urls, lovable_noise_profile="strict")
        self.assertIn("https://lovable.dev/projects/abc", filtered)
        self.assertIn("https://id-preview--abc.lovable.app/path", filtered)
        self.assertIn("https://x.lovableproject.com/hello", filtered)
        self.assertNotIn("https://lovable.devyO", filtered)
        self.assertNotIn("https://lovable.dev116cS", filtered)
        self.assertNotIn("https://lovable.dev4:e", filtered)
        self.assertNotIn("https://lovable.dev", filtered)
        self.assertNotIn("https://lovable.dev/", filtered)
        self.assertNotIn("https://www.lovable.dev", filtered)
        self.assertNotIn("https://www.lovable.dev/", filtered)

    def test_filter_lovable_storage_urls_balanced_salvages_noisy_lovable_dev_variants(self):
        urls = [
            "https://lovable.dev",
            "https://lovable.dev/",
            "https://www.lovable.dev",
            "https://www.lovable.dev/",
            "https://lovable.dev/projects/abc",
            "https://id-preview--abc.lovable.app/path",
            "https://4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lovableproject.",
            "https://id-preview--4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lov",
            "https://lovable.devyO",
            "https://lovable.dev116cS",
            "https://lovable.dev4:e",
        ]
        filtered = _filter_lovable_storage_urls(urls, lovable_noise_profile="balanced")
        self.assertIn("https://lovable.dev/projects/abc", filtered)
        self.assertIn("https://id-preview--abc.lovable.app/path", filtered)
        self.assertIn("https://4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lovableproject.com", filtered)
        self.assertIn("https://id-preview--4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lovable.app", filtered)
        self.assertNotIn("https://lovable.dev", filtered)
        self.assertNotIn("https://lovable.dev/", filtered)
        self.assertNotIn("https://www.lovable.dev", filtered)
        self.assertNotIn("https://www.lovable.dev/", filtered)

    def test_trim_lovable_url_blob_suffix_strips_leveldb_junk(self):
        raw = "https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/^0https://lovable.dev"
        self.assertEqual(
            _trim_lovable_url_blob_suffix(raw),
            "https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/",
        )

    def test_pick_storage_urls_prefers_last_written_project_uuid(self):
        blob = (
            b"older https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/ "
            + b"padding " * 20
            + b"newer https://8614fa76-4875-4307-96bf-0c58a76fb0bd.lovableproject.com/ tail"
        )
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1)
        self.assertEqual(len(picked), 1)
        self.assertIn("8614fa76", picked[0])
        self.assertNotIn("80f778b5", picked[0])

    def test_merge_storage_events_collapses_same_uuid_file_burst(self):
        ts = datetime(2026, 6, 11, 9, 48, tzinfo=timezone.utc)
        events = [
            {
                "timestamp": ts,
                "detail": "storage signal — https://62146e85-26f9-4cf9-b3f2-601c44411dda.lovable.app/",
            },
            {
                "timestamp": ts,
                "detail": (
                    "Project Alpha — Horse Haven — "
                    "https://62146e85-26f9-4cf9-b3f2-601c44411dda.lovableproject.com/"
                ),
                "project": "project-alpha",
            },
        ]
        merged = _merge_storage_events(events, merge_seconds=900)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["project"], "project-alpha")
        self.assertIn("62146e85", merged[0]["detail"])

    def test_merge_storage_events_keeps_distinct_uuids_within_window(self):
        ts = datetime(2026, 6, 11, 9, 48, tzinfo=timezone.utc)
        events = [
            {
                "timestamp": ts,
                "project": "project-alpha",
                "detail": (
                    "project-alpha — Horse Haven — "
                    "https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/"
                ),
            },
            {
                "timestamp": ts,
                "project": "Uncategorized",
                "detail": (
                    "unmapped Lovable (62146e85…) — map UUID via gittan review — "
                    "https://62146e85-26f9-4cf9-b3f2-601c44411dda.lovableproject.com/"
                ),
            },
        ]
        merged = _merge_storage_events(events, merge_seconds=900)
        self.assertEqual(len(merged), 2)
        details = " ".join(event["detail"] for event in merged)
        self.assertIn("80f778b5", details)
        self.assertIn("62146e85", details)

    def test_pick_storage_urls_reads_bare_leveldb_uuid_tokens(self):
        # Bare UUID tokens still count when they are not sticky editor-store keys.
        blob = b"prefix " * 7000 + b"active-project-62146e85-26f9-4cf9-b3f2-601c44411dda\x00tail"
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1, tail_bytes=768)
        self.assertEqual(len(picked), 1)
        self.assertIn("62146e85", picked[0])

    def test_pick_storage_urls_skips_sticky_editor_store_uuids(self):
        # editor-store-<uuid> persists after the tab closes; LevelDB key order can
        # put it in the physical tail while another project is actually open.
        blob = (
            b"prefix " * 7000
            + b"https://85f3c1b3-64e9-4296-85f4-10dc31037933.lovableproject.com/ "
            + b"editor-store-93be36fa-0cb1-4113-9d77-af5a6a1625a0\x00tail"
        )
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1, tail_bytes=768)
        self.assertEqual(len(picked), 1)
        self.assertIn("85f3c1b3", picked[0])
        self.assertNotIn("93be36fa", picked[0])

    def test_storage_signal_files_use_wal_logs_not_sstables(self):
        from collectors.lovable_desktop import _storage_signal_files

        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = lovable_desktop_root(home)
            leveldb = root / "Local Storage" / "leveldb"
            leveldb.mkdir(parents=True)
            (leveldb / "001665.ldb").write_bytes(b"editor-store-93be36fa-0cb1-4113-9d77-af5a6a1625a0")
            (leveldb / "MANIFEST-000001").write_bytes(b"https://93be36fa-0cb1-4113-9d77-af5a6a1625a0.lovableproject.com/")
            wal = leveldb / "001668.log"
            wal.write_bytes(b"https://85f3c1b3-64e9-4296-85f4-10dc31037933.lovableproject.com/")
            files = _storage_signal_files(home)
            self.assertEqual(files, [wal])

    def test_pick_storage_urls_skips_nil_and_non_v4_uuids(self):
        blob = (
            b"prefix " * 7000
            + b"https://00000000-0000-0000-0000-000000000000.lovableproject.com/ "
            + b"https://019f8f41-fa60-7a26-85d1-348d7e94480d.lovableproject.com/ "
            + b"https://85f3c1b3-64e9-4296-85f4-10dc31037933.lovableproject.com/ tail"
        )
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=3, tail_bytes=768)
        self.assertEqual(len(picked), 1)
        self.assertIn("85f3c1b3", picked[0])

    def test_pick_storage_urls_skips_rudderstack_analytics_uuids(self):
        # RudderStack queue keys (rudder_<writeKey>.<uuid>.ack/.reclaimStart) are
        # telemetry message ids, not Lovable projects — they must not fabricate
        # "unmapped Lovable" rows.
        blob = (
            b"prefix " * 7000
            + b"rudder_30uiF44drV1UnRmUEUVhfQ2L500."
            + b"62146e85-26f9-4cf9-b3f2-601c44411dda.ack\x00tail"
        )
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1, tail_bytes=768)
        self.assertEqual(picked, [])

    def test_pick_storage_urls_prefers_real_project_over_analytics_uuid_in_tail(self):
        # A genuine project URL in the tail must win even when a rudder queue id
        # was written later in the same blob.
        blob = (
            b"prefix " * 7000
            + b"https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/ "
            + b"rudder_30uiF44drV1UnRmUEUVhfQ2L500."
            + b"62146e85-26f9-4cf9-b3f2-601c44411dda.reclaimEnd\x00tail"
        )
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1, tail_bytes=768)
        self.assertEqual(len(picked), 1)
        self.assertIn("80f778b5", picked[0])
        self.assertNotIn("62146e85", picked[0])

    def test_pick_storage_urls_prefers_tracked_profile_uuid_over_newer_tail(self):
        prefix = b"x" * 54_000
        tail = (
            b"https://121726c8-b8f3-4a58-8b27-08104baf8fa5.lovableproject.com/ "
            b"https://810513a4-6676-4f18-ae92-097467e52d98.lovableproject.com/ end"
        )
        blob = prefix + tail
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        profiles = [
            {
                "name": "timelog-extract",
                "match_terms": ["121726c8-b8f3-4a58-8b27-08104baf8fa5"],
                "tracked_urls": [],
            }
        ]
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1, tail_bytes=768, profiles=profiles)
        self.assertEqual(len(picked), 1)
        self.assertIn("121726c8", picked[0])

    def test_pick_storage_urls_ignores_mapped_uuid_outside_tail(self):
        # Mimics a LevelDB touch: many historical UUIDs remain in-file, but only the
        # tail write (new unmapped project) should surface as a storage signal.
        prefix = b"x" * 54_000
        tail = (
            b"https://121726c8-b8f3-4a58-8b27-08104baf8fa5.lovableproject.com/ "
            b"https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/ "
            b"https://62146e85-26f9-4cf9-b3f2-601c44411dda.lovableproject.com/ end"
        )
        blob = prefix + tail
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1, tail_bytes=768)
        self.assertEqual(len(picked), 1)
        self.assertIn("62146e85", picked[0])
        self.assertNotIn("80f778b5", picked[0])
        self.assertNotIn("121726c8", picked[0])

    def test_pick_storage_urls_survives_bracket_junk_urls(self):
        # urlparse raises ValueError on bracket fragments from binary blobs;
        # the UUID key helper must swallow that instead of crashing the collector.
        blob = (
            b"prefix " * 7000
            + b"https://[aa.lovableproject.com/x "
            + b"https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/ tail"
        )
        urls = _filter_lovable_storage_urls(_extract_lovable_urls(blob), lovable_noise_profile="balanced")
        picked = _pick_storage_urls_from_blob(blob, urls, limit=1, tail_bytes=768)
        self.assertEqual(len(picked), 1)
        self.assertIn("80f778b5", picked[0])

    def test_filter_lovable_storage_urls_balanced_skips_malformed_urls_without_crashing(self):
        urls = [
            "https://lovable.dev/projects/abc",
            "https://[broken-url",
        ]
        filtered = _filter_lovable_storage_urls(urls, lovable_noise_profile="balanced")
        self.assertIn("https://lovable.dev/projects/abc", filtered)
        self.assertNotIn("https://[broken-url", filtered)

    def test_collect_lovable_desktop_falls_back_to_storage_when_history_has_no_rows(self):
        dt = datetime.now(timezone.utc)
        sentinel = [{"source": "Lovable (desktop)", "detail": "storage signal — x", "project": "Time Log Genius"}]
        with patch("collectors.lovable_desktop.lovable_desktop_history_candidates", return_value=[Path("/tmp/History")]):
            with patch("collectors.lovable_desktop.query_chrome", return_value=[]):
                with patch("collectors.lovable_desktop._collect_lovable_desktop_from_storage", return_value=sentinel) as fb:
                    out = collect_lovable_desktop(
                        profiles=[],
                        dt_from=dt,
                        dt_to=dt,
                        collapse_minutes=15,
                        home=Path("/tmp"),
                        epoch_delta_us=0,
                        classify_project=lambda text, profiles: "Unknown",
                        make_event=lambda source, ts, detail, project: {
                            "source": source,
                            "local_ts": ts,
                            "detail": detail,
                            "project": project,
                        },
                        lovable_noise_profile="balanced",
                    )
        self.assertEqual(out, sentinel)
        fb.assert_called_once()


if __name__ == "__main__":
    unittest.main()
