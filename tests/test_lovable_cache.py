"""Tests for Lovable Desktop cache-mtime evidence (GH-145)."""

from __future__ import annotations

import json
import os
import struct
import unittest
import unittest.mock
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from collectors.lovable_cache import (
    collect_lovable_cache_events,
    load_lovable_project_titles,
    lovable_cache_status,
)
from collectors.lovable_desktop import (
    _collect_lovable_desktop_from_storage,
    _format_lovable_event_detail,
    _merge_storage_events,
    lovable_desktop_root,
)

_ENTRY_MAGIC = 0xFCFB6D1BA7725C30
_EOF_MAGIC = 0xF4FA6F45970D41D8
_PROJECT_ALPHA = "8e18db4d-9577-4cc7-a54a-4685b09cef3d"
_RUDDER_UUID = "62146e85-26f9-4cf9-b3f2-601c44411dda"


def _make_entry(key: str, body: bytes) -> bytes:
    kb = key.encode("utf-8")
    return (
        struct.pack("<QIII", _ENTRY_MAGIC, 1, len(kb), 0)
        + kb
        + body
        + struct.pack("<Q", _EOF_MAGIC)
    )


def _classify(text, profiles):
    if "project-alpha" in text or _PROJECT_ALPHA in text:
        return "project-alpha"
    return "Uncategorized"


class LovableCacheTests(unittest.TestCase):
    def test_format_lovable_event_detail_prefers_human_title(self):
        detail = _format_lovable_event_detail(
            "project-alpha",
            f"https://{_PROJECT_ALPHA}.lovableproject.com/",
            display_title="Project Alpha",
        )
        self.assertEqual(detail, "project-alpha — Project Alpha")

    def test_format_lovable_event_detail_unmapped_title_keeps_map_nudge(self):
        detail = _format_lovable_event_detail(
            "Uncategorized",
            f"https://{_PROJECT_ALPHA}.lovableproject.com/",
            display_title="Project Alpha",
        )
        self.assertIn("Project Alpha", detail)
        self.assertIn("map UUID via gittan review", detail)

    def test_merge_storage_events_prefers_mapped_same_uuid(self):
        ts = datetime(2026, 6, 11, 10, 11, tzinfo=timezone.utc)
        ts2 = datetime(2026, 6, 11, 10, 14, tzinfo=timezone.utc)
        uuid = "d7afafcd-1b04-4306-93be-b91f00000000"
        mapped = {
            "timestamp": ts,
            "project": "project-alpha",
            "detail": f"project-alpha — Project Alpha — https://{uuid}.lovableproject.com/",
            "source": "Lovable (desktop)",
        }
        unmapped = {
            "timestamp": ts2,
            "project": "Uncategorized",
            "detail": (
                f"unmapped Lovable (d7afafcd…) — map UUID via gittan review — "
                f"https://{uuid}.lovableproject.com/"
            ),
            "source": "Lovable (desktop)",
        }
        merged = _merge_storage_events([unmapped, mapped], merge_seconds=900)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["project"], "project-alpha")

    def test_merge_storage_events_keeps_mapped_and_unmapped_distinct_uuids(self):
        ts = datetime(2026, 6, 11, 10, 11, tzinfo=timezone.utc)
        ts2 = datetime(2026, 6, 11, 10, 14, tzinfo=timezone.utc)
        mapped = {
            "timestamp": ts,
            "project": "project-alpha",
            "detail": (
                "project-alpha — Project Alpha App — "
                "https://80f778b5-230c-461d-9ff3-169a22ad2c01.lovableproject.com/"
            ),
            "source": "Lovable (desktop)",
        }
        unmapped = {
            "timestamp": ts2,
            "project": "Uncategorized",
            "detail": (
                "unmapped Lovable (d7afafcd…) — map UUID via gittan review — "
                "https://d7afafcd-1b04-4306-93be-b91f00000000.lovableproject.com/"
            ),
            "source": "Lovable (desktop)",
        }
        merged = _merge_storage_events([unmapped, mapped], merge_seconds=900)
        self.assertEqual(len(merged), 2)
        projects = {event["project"] for event in merged}
        self.assertEqual(projects, {"project-alpha", "Uncategorized"})
        details = " ".join(event["detail"] for event in merged)
        self.assertIn("80f778b5", details)
        self.assertIn("d7afafcd", details)

    def test_load_lovable_project_titles_from_projects_search_cache(self):
        payload = json.dumps(
            {
                "projects": [
                    {"id": _PROJECT_ALPHA, "display_name": "Project Alpha", "edit_count": 3},
                ]
            }
        ).encode("utf-8")
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            (cache_dir / "search_0").write_bytes(
                _make_entry(
                    "1/0/https://api.lovable.dev/workspaces/ws/projects/search",
                    payload,
                )
            )
            titles = load_lovable_project_titles(home)
        self.assertEqual(titles[_PROJECT_ALPHA], "Project Alpha")

    def test_cache_mtime_event_uses_display_title(self):
        morning = datetime(2026, 6, 11, 9, 40, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            search_path = cache_dir / "search_0"
            search_path.write_bytes(
                _make_entry(
                    "1/0/https://api.lovable.dev/workspaces/ws/projects/search",
                    json.dumps(
                        {"projects": [{"id": _PROJECT_ALPHA, "display_name": "Project Alpha"}]}
                    ).encode("utf-8"),
                )
            )
            activity_path = cache_dir / "activity_0"
            activity_path.write_bytes(
                _make_entry(
                    f"1/0/https://lovable.dev/projects/{_PROJECT_ALPHA}",
                    b"analytics payload",
                )
            )
            os.utime(activity_path, (morning.timestamp(), morning.timestamp()))
            events = collect_lovable_cache_events(
                profiles=[],
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=_classify,
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
        self.assertEqual(len(events), 1)
        self.assertIn("Project Alpha", events[0]["detail"])
        self.assertEqual(events[0]["timestamp"], morning)

    def test_cache_morning_visible_when_storage_touch_is_late(self):
        morning = datetime(2026, 6, 11, 9, 40, tzinfo=timezone.utc)
        evening = datetime(2026, 6, 11, 18, 45, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            activity_path = cache_dir / "activity_0"
            activity_path.write_bytes(
                f"https://lovable.dev/projects/{_PROJECT_ALPHA}&tiba=Project+Alpha".encode("utf-8")
            )
            os.utime(activity_path, (morning.timestamp(), morning.timestamp()))

            storage_dir = lovable_desktop_root(home) / "Local Storage" / "leveldb"
            storage_dir.mkdir(parents=True)
            # WAL ``.log`` only — compacted ``.ldb`` is ignored (key-sorted ≠ write order).
            storage_path = storage_dir / "000003.log"
            storage_path.write_bytes(b"x" * 8000 + f"https://{_PROJECT_ALPHA}.lovableproject.com/".encode())
            os.utime(storage_path, (evening.timestamp(), evening.timestamp()))

            events = _collect_lovable_desktop_from_storage(
                profiles=[{"name": "project-alpha", "match_terms": [_PROJECT_ALPHA]}],
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=_classify,
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
        hours = {event["timestamp"].hour for event in events}
        self.assertIn(9, hours)
        self.assertIn(18, hours)

    def test_title_and_event_scan_share_reads_no_duplicate_disk_io(self):
        """load_lovable_project_titles (unfiltered) and collect_lovable_cache_events
        (date-filtered) both walk Cache_Data; each file must be read once total."""
        morning = datetime(2026, 6, 11, 9, 40, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            search_path = cache_dir / "search_0"
            search_path.write_bytes(
                _make_entry(
                    "1/0/https://api.lovable.dev/workspaces/ws/projects/search",
                    json.dumps(
                        {"projects": [{"id": _PROJECT_ALPHA, "display_name": "Project Alpha"}]}
                    ).encode("utf-8"),
                )
            )
            activity_path = cache_dir / "activity_0"
            activity_path.write_bytes(
                _make_entry(f"1/0/https://lovable.dev/projects/{_PROJECT_ALPHA}", b"analytics payload")
            )
            os.utime(activity_path, (morning.timestamp(), morning.timestamp()))

            read_counts: dict[Path, int] = {}
            original_read_bytes = Path.read_bytes

            def counting_read_bytes(self_path: Path) -> bytes:
                read_counts[self_path] = read_counts.get(self_path, 0) + 1
                return original_read_bytes(self_path)

            with unittest.mock.patch.object(Path, "read_bytes", counting_read_bytes):
                events = _collect_lovable_desktop_from_storage(
                    profiles=[{"name": "project-alpha", "match_terms": [_PROJECT_ALPHA]}],
                    dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                    dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                    home=home,
                    classify_project=_classify,
                    make_event=lambda source, ts, detail, project: {
                        "source": source,
                        "timestamp": ts,
                        "detail": detail,
                        "project": project,
                    },
                )

        self.assertTrue(events)
        self.assertIn("Project Alpha", events[0]["detail"])
        duplicated = {path: count for path, count in read_counts.items() if count > 1}
        self.assertEqual(duplicated, {}, f"files read from disk more than once: {duplicated}")

    def test_cache_scan_skips_rudderstack_uuid(self):
        ts = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            cache_path = cache_dir / "rudder_0"
            cache_path.write_bytes(
                b"rudder_30uiF44drV1UnRmUEUVhfQ2L500."
                + _RUDDER_UUID.encode("ascii")
                + b".ack"
            )
            os.utime(cache_path, (ts.timestamp(), ts.timestamp()))
            events = collect_lovable_cache_events(
                profiles=[],
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=_classify,
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
        self.assertEqual(events, [])

    def test_cache_scan_skips_bare_uuid_noise_without_project_url(self):
        ts = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
        junk = "00000000-0000-0000-0000-000000000000"
        noise = "019f8f41-fa60-7a26-85d1-348d7e94480d"
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            cache_path = cache_dir / "noise_0"
            cache_path.write_bytes(
                f"pad {junk} pad {noise} pad {_PROJECT_ALPHA} pad".encode("utf-8")
            )
            os.utime(cache_path, (ts.timestamp(), ts.timestamp()))
            events = collect_lovable_cache_events(
                profiles=[],
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=_classify,
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
        self.assertEqual(events, [])

    def test_cache_scan_skips_oversized_file(self):
        ts = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            cache_path = cache_dir / "big_0"
            cache_path.write_bytes(b"x" * (6 * 1024 * 1024))
            os.utime(cache_path, (ts.timestamp(), ts.timestamp()))
            events = collect_lovable_cache_events(
                profiles=[],
                dt_from=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc),
                home=home,
                classify_project=_classify,
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
            )
        self.assertEqual(events, [])

    def test_lovable_cache_status_reports_readable_cache(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache_dir = lovable_desktop_root(home) / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            (cache_dir / "search_0").write_bytes(
                _make_entry(
                    "1/0/https://api.lovable.dev/workspaces/ws/projects/search",
                    json.dumps(
                        {"projects": [{"id": _PROJECT_ALPHA, "display_name": "Project Alpha"}]}
                    ).encode("utf-8"),
                )
            )
            ok, reason = lovable_cache_status(home)
        self.assertTrue(ok)
        self.assertIn("project titles", reason)


if __name__ == "__main__":
    unittest.main()
