import struct
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from core.chromium_cache import (
    codec_available,
    iter_cache_entries,
    read_cache_entry,
)

_ENTRY_MAGIC = 0xFCFB6D1BA7725C30
_EOF_MAGIC = 0xF4FA6F45970D41D8


def _make_entry(key: str, body: bytes) -> bytes:
    """Build a minimal Chromium simple-cache entry: header + key + body + EOF."""
    kb = key.encode("utf-8")
    header = struct.pack("<QIII", _ENTRY_MAGIC, 1, len(kb), 0)
    eof = struct.pack("<Q", _EOF_MAGIC)
    return header + kb + body + eof


class ChromiumCacheTests(unittest.TestCase):
    def _write(self, d: Path, name: str, key: str, body: bytes) -> Path:
        p = d / f"{name}_0"
        p.write_bytes(_make_entry(key, body))
        return p

    def test_identity_json_body(self) -> None:
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            key = "1/0/https://claude.ai/v1/sessions/session_abc/events?limit=500"
            self._write(d, "aaaa", key, b'{"data":[]}')
            entry = read_cache_entry(d / "aaaa_0")
            self.assertIsNotNone(entry)
            self.assertIn("/v1/sessions/session_abc/events", entry.key)
            self.assertEqual(entry.body, b'{"data":[]}')

    def test_key_substr_gate_skips_decode(self) -> None:
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            self._write(d, "bbbb", "1/0/https://claude.ai/other", b'{"x":1}')
            # Non-matching substring → None (and body never decoded).
            self.assertIsNone(read_cache_entry(d / "bbbb_0", key_substr="/v1/sessions/"))
            # Matching substring → returned.
            self.assertIsNotNone(read_cache_entry(d / "bbbb_0", key_substr="/other"))

    def test_foreign_or_corrupt_file_is_skipped(self) -> None:
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "junk_0").write_bytes(b"not a chromium cache entry at all")
            (d / "tiny_0").write_bytes(b"\x00\x01")
            self.assertIsNone(read_cache_entry(d / "junk_0"))
            self.assertIsNone(read_cache_entry(d / "tiny_0"))

    def test_iter_filters_by_key_and_mtime(self) -> None:
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            self._write(d, "match", "1/0/https://x/v1/sessions/s1/events", b'{"data":1}')
            self._write(d, "nomatch", "1/0/https://x/v1/projects/p1", b'{"data":2}')
            keys = [e.key for e in iter_cache_entries(d, "/v1/sessions/")]
            self.assertEqual(len(keys), 1)
            self.assertIn("/v1/sessions/s1/events", keys[0])
            # mtime filter in the future → nothing.
            future = datetime.now(timezone.utc) + timedelta(days=1)
            self.assertEqual(list(iter_cache_entries(d, "/v1/sessions/", newer_than=future)), [])

    @unittest.skipUnless(codec_available()["zstd"], "zstandard not installed")
    def test_zstd_body_roundtrip(self) -> None:
        import zstandard

        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            payload = b'{"data":[{"created_at":"2026-06-11T06:51:00Z","type":"user"}]}'
            zbody = zstandard.ZstdCompressor().compress(payload)
            self._write(d, "zz", "1/0/https://claude.ai/v1/sessions/s/events", zbody)
            entry = read_cache_entry(d / "zz_0")
            self.assertIsNotNone(entry)
            self.assertEqual(entry.body, payload)


if __name__ == "__main__":
    unittest.main()
