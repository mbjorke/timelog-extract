"""Read Chromium "simple cache" entries from Electron desktop apps.

Some Electron desktop apps (Claude Desktop, Lovable Desktop) keep their real
activity **server-side** and leave it locally only in the Chromium HTTP disk
cache (``Cache/Cache_Data/*_0``). Response bodies are compressed with modern
codecs — Claude uses **zstd**, Lovable uses **brotli**. This module parses the
simple-cache entry format and returns the decoded body, so each collector only
has to supply a URL-key filter and its own field extraction.

Scope: this is a *last-resort* source for apps with no first-class local log.
IDE forks (Cursor/Windsurf/Antigravity/Codex) and CLIs (Claude Code/Gemini/
Codex) write structured logs and must never be cache-scraped.

Codecs are **optional**: ``brotli`` / ``zstandard`` are binary wheels. If a
needed codec is not importable, the affected entry is skipped (no crash), and
``codec_available()`` lets callers surface a ``gittan doctor`` hint.
"""

from __future__ import annotations

import io
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# Chromium simple-cache entry framing (little-endian).
_ENTRY_MAGIC = 0xFCFB6D1BA7725C30
_EOF_MAGIC = 0xF4FA6F45970D41D8
_HEADER_FMT = "<QIII"  # magic(8) version(4) key_len(4) key_hash(4)
_HEADER_SIZE = 24

# Compression stream markers.
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_GZIP_MAGIC = b"\x1f\x8b\x08"

# Defensive cap: cache bodies of interest are small (compressed); skip giant
# blobs (e.g. multi-MB Local Storage snapshots) before reading them.
_DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024
# Decompression-bomb guard for the decoded body.
_MAX_DECODED_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class CacheEntry:
    """A decoded Chromium cache entry."""

    key: str
    mtime: datetime
    body: bytes


def _import_zstd():
    try:
        import zstandard  # type: ignore

        return zstandard
    except ImportError:
        return None


def _import_brotli():
    try:
        import brotli  # type: ignore

        return brotli
    except ImportError:
        return None


def codec_available() -> dict[str, bool]:
    """Which optional decompression codecs are importable right now."""
    return {"zstd": _import_zstd() is not None, "brotli": _import_brotli() is not None}


def _decode_body(after_key: bytes) -> Optional[bytes]:
    """Decode the response body from the post-key region of a cache entry.

    Tries codecs in order: zstd (by magic), gzip (by magic), brotli (no magic,
    so offset attempts within the first stream), then identity JSON. Returns
    None when no codec applies or the needed codec is unavailable.
    """
    eof = after_key.find(struct.pack("<Q", _EOF_MAGIC))
    body_region = after_key[:eof] if eof > 0 else after_key

    # zstd: locate frame magic anywhere in the post-key bytes. Read one byte
    # past the cap so an over-cap stream is rejected, not silently truncated.
    zi = after_key.find(_ZSTD_MAGIC)
    if zi >= 0:
        zstd = _import_zstd()
        if zstd is not None:
            try:
                reader = zstd.ZstdDecompressor().stream_reader(io.BytesIO(after_key[zi:]))
                out = reader.read(_MAX_DECODED_BYTES + 1)
                if 0 < len(out) <= _MAX_DECODED_BYTES:
                    return out
            except Exception:
                pass

    # gzip: magic-prefixed deflate stream, decoded with a bounded decompressor.
    gi = after_key.find(_GZIP_MAGIC)
    if gi >= 0:
        try:
            decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
            out = decomp.decompress(after_key[gi:], _MAX_DECODED_BYTES + 1)
            if 0 < len(out) <= _MAX_DECODED_BYTES:
                return out
        except Exception:
            pass

    # brotli has no header magic; try a few leading-byte offsets of the stream.
    brotli = _import_brotli()
    if brotli is not None:
        for skip in range(0, 8):
            try:
                out = brotli.decompress(body_region[skip:])
                if 0 < len(out) <= _MAX_DECODED_BYTES:
                    return out
            except Exception:
                continue

    # identity: body already plain JSON at the start of the stream.
    for marker in (b"{", b"["):
        k = body_region.find(marker)
        if 0 <= k < 8:
            return body_region[k:]
    return None


def _split_key(raw: bytes) -> Optional[tuple[str, bytes]]:
    """Validate the simple-cache header and split (key, post-key bytes)."""
    if len(raw) < _HEADER_SIZE:
        return None
    try:
        magic, _version, key_len, _key_hash = struct.unpack(_HEADER_FMT, raw[:20])
    except struct.error:
        return None
    if magic != _ENTRY_MAGIC or key_len <= 0:
        return None
    key_end = 20 + key_len
    if key_end > len(raw):
        return None
    return raw[20:key_end].decode("utf-8", "ignore"), raw[key_end:]


def read_cache_entry(
    path: Path,
    *,
    key_substr: str = "",
    key_predicate=None,
) -> Optional[CacheEntry]:
    """Parse one ``*_0`` simple-cache file → CacheEntry, or None.

    The body is decoded only when the key contains ``key_substr`` (empty matches
    all) and satisfies ``key_predicate`` (when given), so a non-matching entry
    never pays the decompression cost. Never raises on malformed/binary/evicted
    entries; returns None instead.
    """
    try:
        if path.stat().st_size > _DEFAULT_MAX_FILE_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    split = _split_key(raw)
    if split is None:
        return None
    key, after_key = split
    if key_substr and key_substr not in key:
        return None
    if key_predicate is not None and not key_predicate(key):
        return None
    body = _decode_body(after_key)
    if body is None:
        return None
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None
    return CacheEntry(key=key, mtime=mtime, body=body)


def iter_cache_entries(
    cache_dir: Path,
    key_substr: str,
    *,
    newer_than: Optional[datetime] = None,
    key_predicate=None,
) -> Iterator[CacheEntry]:
    """Yield decoded cache entries whose key contains ``key_substr``.

    ``newer_than`` (aware datetime) filters by file mtime before reading the
    body. Unreadable/foreign entries are skipped silently.
    """
    if not cache_dir.is_dir():
        return
    for path in cache_dir.iterdir():
        if not path.name.endswith("_0") or not path.is_file():
            continue
        if newer_than is not None:
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                continue
            if mtime < newer_than:
                continue
        entry = read_cache_entry(path, key_substr=key_substr, key_predicate=key_predicate)
        if entry is not None:
            yield entry
