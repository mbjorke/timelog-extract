import json
import struct
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from collectors.claude_desktop_events import (
    CLAUDE_DESKTOP_CODE_SOURCE,
    claude_events_cache_status,
    collect_claude_desktop_code,
)
from core.chromium_cache import codec_available

_ENTRY_MAGIC = 0xFCFB6D1BA7725C30
_EOF_MAGIC = 0xF4FA6F45970D41D8

_SECRET_TEXT = "TOP-SECRET customer message body that must never leak"


def _make_entry(key: str, body: bytes) -> bytes:
    kb = key.encode("utf-8")
    return (
        struct.pack("<QIII", _ENTRY_MAGIC, 1, len(kb), 0)
        + kb
        + body
        + struct.pack("<Q", _EOF_MAGIC)
    )


def _events_payload(session_id: str, stamps: list[datetime], cwd: str) -> bytes:
    data = []
    for i, ts in enumerate(stamps):
        ev = {
            "uuid": f"{session_id}-ev-{i}",
            "session_id": session_id,
            "type": "user" if i % 2 == 0 else "assistant",
            "created_at": ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "message": {"content": _SECRET_TEXT},
        }
        if i == 0:
            ev["cwd"] = cwd
        data.append(ev)
    return json.dumps({"data": data, "has_more": False}).encode("utf-8")


def _classify(text, profiles):
    return "project-alpha" if "project-alpha" in text else "Uncategorized"


def _make_event(source, ts, detail, project, anchors=None):
    event = {"source": source, "timestamp": ts, "detail": detail, "project": project}
    if anchors:
        event["anchors"] = anchors
    return event


def _write_cache(home: Path, name: str, key: str, body: bytes) -> Path:
    cache = home / "Library" / "Application Support" / "Claude" / "Cache" / "Cache_Data"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{name}_0"
    path.write_bytes(_make_entry(key, body))
    return path


class ClaudeDesktopEventsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.dt_from = datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc)
        self.dt_to = datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _collect(self):
        return collect_claude_desktop_code(
            [], self.dt_from, self.dt_to, self.home, _classify, _make_event
        )

    def test_no_cache_dir_returns_empty(self) -> None:
        self.assertEqual(self._collect(), [])
        usable, reason = claude_events_cache_status(self.home)
        self.assertFalse(usable)
        self.assertIn("No Claude Desktop cache", reason)

    def test_cluster_reconstructs_span_without_message_text(self) -> None:
        base = datetime(2026, 6, 11, 6, 51, tzinfo=timezone.utc)
        # 2h of turns 4 min apart, then a >15-min idle gap, then a short touch.
        stamps = [base + timedelta(minutes=4 * i) for i in range(31)]
        stamps += [base + timedelta(hours=3), base + timedelta(hours=3, minutes=2)]
        body = _events_payload("session_01TESTALPHA", stamps, "/home/user/project-alpha")
        _write_cache(self.home, "events", "1/0/https://claude.ai/v1/sessions/session_01TESTALPHA/events?limit=500", body)

        events = self._collect()
        self.assertTrue(events)
        for ev in events:
            self.assertEqual(ev["source"], CLAUDE_DESKTOP_CODE_SOURCE)
            self.assertEqual(ev["project"], "project-alpha")
            self.assertNotIn(_SECRET_TEXT, ev["detail"])
            self.assertNotIn("TOP-SECRET", json.dumps(ev, default=str))
            self.assertEqual(ev["anchors"], {"dir": "project-alpha"})
        # Span of the first cluster survives thinning: first and last turn kept.
        times = sorted(ev["timestamp"] for ev in events)
        self.assertEqual(times[0], stamps[0])
        self.assertEqual(times[-1], stamps[-1])
        first_cluster = [t for t in times if t <= base + timedelta(hours=2)]
        self.assertGreaterEqual((first_cluster[-1] - first_cluster[0]).total_seconds(), 110 * 60)
        # Two clusters → two distinct turn counts.
        details = {ev["detail"] for ev in events}
        self.assertEqual(details, {"31 turns", "2 turns"})

    def test_internal_uuid_session_merges_with_key_session_id(self) -> None:
        # Real cache bodies mix events carrying an internal session_id UUID
        # with events carrying none; the cache key holds the public
        # session_<id>. All must land in ONE session keyed by the public id,
        # with cwd attribution shared (regression: one session split in two,
        # half Uncategorized).
        base = datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc)
        data = [
            {
                "uuid": "ev-init",
                "type": "system",
                "created_at": base.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "session_id": "1976e51a-5e65-5a0c-bbbb-000000000000",
                "cwd": "/home/user/project-alpha",
            },
            {
                "uuid": "ev-turn-1",
                "type": "user",
                "created_at": (base + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                # no session_id field at all
            },
            {
                "uuid": "ev-turn-2",
                "type": "assistant",
                "created_at": (base + timedelta(minutes=4)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "session_id": "1976e51a-5e65-5a0c-bbbb-000000000000",
            },
        ]
        body = json.dumps({"data": data}).encode("utf-8")
        _write_cache(self.home, "split", "1/0/https://claude.ai/v1/sessions/session_01MERGE/events?limit=500", body)

        events = self._collect()
        details = {ev["detail"] for ev in events}
        self.assertEqual(details, {"2 turns"})
        for ev in events:
            self.assertEqual(ev["project"], "project-alpha")

    def test_session_title_enriches_detail(self) -> None:
        base = datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc)
        body = _events_payload("session_01TITLED", [base, base + timedelta(minutes=2)], "/home/user/project-alpha")
        _write_cache(self.home, "ev", "1/0/https://claude.ai/v1/sessions/session_01TITLED/events?limit=500", body)
        meta = json.dumps(
            {"id": "session_01TITLED", "title": "Build dashboard MVP", "session_status": "idle"}
        ).encode("utf-8")
        _write_cache(self.home, "meta", "1/0/https://claude.ai/v1/sessions/session_01TITLED", meta)

        events = self._collect()
        details = {ev["detail"] for ev in events}
        self.assertEqual(details, {"2 turns"})
        self.assertEqual(events[0]["anchors"].get("label"), "Build dashboard MVP")

    def test_session_metadata_repo_slug_attributes_project(self) -> None:
        # Session metadata carries an explicit owner/repo in git outcomes —
        # worktree-invariant attribution even when cwd is a sandbox path.
        base = datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc)
        body = _events_payload("session_01SLUG", [base, base + timedelta(minutes=2)], "/home/user/sandbox")
        _write_cache(self.home, "ev2", "1/0/https://claude.ai/v1/sessions/session_01SLUG/events?limit=500", body)
        meta = json.dumps(
            {
                "id": "session_01SLUG",
                "title": "Fix the widget",
                "session_context": {
                    "outcomes": [
                        {
                            "type": "git_repository",
                            "git_info": {"repo": "owner-a/project-alpha", "type": "github"},
                        }
                    ]
                },
            }
        ).encode("utf-8")
        _write_cache(self.home, "meta2", "1/0/https://claude.ai/v1/sessions/session_01SLUG", meta)

        events = self._collect()
        self.assertTrue(events)
        for ev in events:
            self.assertEqual(ev["project"], "project-alpha")
            self.assertEqual(ev["anchors"].get("repo"), "owner-a/project-alpha")

    def test_background_only_cluster_emits_nothing(self) -> None:
        # Clusters with zero user/assistant turns (rate-limit pings, env
        # refreshes) must not claim hours.
        base = datetime(2026, 6, 11, 13, 13, tzinfo=timezone.utc)
        data = [
            {
                "uuid": f"bg-{i}",
                "type": "rate_limit_event",
                "created_at": (base + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "session_id": "sess-bg",
            }
            for i in range(3)
        ]
        body = json.dumps({"data": data}).encode("utf-8")
        _write_cache(self.home, "bg", "1/0/https://claude.ai/v1/sessions/session_01BG/events", body)
        self.assertEqual(self._collect(), [])

    def test_duplicate_uuids_across_entries_counted_once(self) -> None:
        base = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
        stamps = [base + timedelta(minutes=i) for i in range(3)]
        body = _events_payload("session_01DUP", stamps, "/home/user/project-alpha")
        _write_cache(self.home, "page1", "1/0/https://claude.ai/v1/sessions/session_01DUP/events?limit=500", body)
        _write_cache(self.home, "page2", "1/0/https://claude.ai/v1/sessions/session_01DUP/events?limit=500&after_id=x", body)

        events = self._collect()
        details = {ev["detail"] for ev in events}
        self.assertEqual(details, {"3 turns"})

    def test_events_and_meta_scan_share_reads_no_duplicate_disk_io(self) -> None:
        """The events pass and the metadata pass (_session_meta) both walk
        cache_dir; each file must be read from disk at most once total."""
        base = datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc)
        body = _events_payload("session_01SHARED", [base, base + timedelta(minutes=2)], "/home/user/project-alpha")
        _write_cache(
            self.home, "ev-shared", "1/0/https://claude.ai/v1/sessions/session_01SHARED/events?limit=500", body
        )
        meta = json.dumps({"id": "session_01SHARED", "title": "Shared read title"}).encode("utf-8")
        _write_cache(self.home, "meta-shared", "1/0/https://claude.ai/v1/sessions/session_01SHARED", meta)

        read_counts: dict[Path, int] = {}
        original_read_bytes = Path.read_bytes

        def counting_read_bytes(self_path: Path) -> bytes:
            read_counts[self_path] = read_counts.get(self_path, 0) + 1
            return original_read_bytes(self_path)

        with unittest.mock.patch.object(Path, "read_bytes", counting_read_bytes):
            events = self._collect()

        self.assertTrue(events)
        self.assertEqual(events[0]["anchors"].get("label"), "Shared read title")
        duplicated = {path: count for path, count in read_counts.items() if count > 1}
        self.assertEqual(duplicated, {}, f"files read from disk more than once: {duplicated}")

    def test_corrupt_and_foreign_entries_are_skipped(self) -> None:
        cache = self.home / "Library" / "Application Support" / "Claude" / "Cache" / "Cache_Data"
        cache.mkdir(parents=True)
        (cache / "junk_0").write_bytes(b"\x00\x01\x02 definitely not a cache entry")
        _write_cache(self.home, "trunc", "1/0/https://claude.ai/v1/sessions/s/events", b"{not-json")
        self.assertEqual(self._collect(), [])

    def test_out_of_window_events_excluded(self) -> None:
        old = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        body = _events_payload("session_01OLD", [old, old + timedelta(minutes=5)], "/home/user/project-alpha")
        path = _write_cache(self.home, "old", "1/0/https://claude.ai/v1/sessions/session_01OLD/events", body)
        # Keep the file mtime inside the scan window so only created_at filters.
        self.assertTrue(path.exists())
        self.assertEqual(self._collect(), [])

    @unittest.skipUnless(codec_available()["zstd"], "zstandard not installed")
    def test_zstd_compressed_body_decodes(self) -> None:
        import zstandard

        base = datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc)
        raw = _events_payload("session_01Z", [base, base + timedelta(minutes=3)], "/home/user/project-alpha")
        _write_cache(
            self.home,
            "zz",
            "1/0/https://claude.ai/v1/sessions/session_01Z/events",
            zstandard.ZstdCompressor().compress(raw),
        )
        events = self._collect()
        self.assertTrue(events)
        self.assertEqual(events[0]["detail"], "2 turns")


if __name__ == "__main__":
    unittest.main()
