"""Claude Desktop (Code) is capturable, and its repo anchor survives capture.

Measured 2026-07-26 (`docs/evals/claude-surface-attribution-measurement.md`):
desktop Code mode carries a worktree-invariant repo slug from session metadata,
which makes it the one chat-shaped surface that attributes itself. These tests
pin that the anchor still holds once the events go through capture, and that
plain desktop chat stays out of `CAPTURE_SOURCES`.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_claude_desktop_events import _make_entry

from core.evidence_store import events_dir, read_records
from core.session_capture import CAPTURE_SOURCES, capture_device_evidence

PROFILES = [
    {
        "name": "gittan",
        "project_id": "gittan",
        "match_terms": ["timelog-extract", "gittan"],
        "tracked_urls": [],
        "aliases": [],
        "canonical_project": "gittan",
        "customer": "internal",
        "email": "",
        "tags": [],
    }
]

BASE = datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc)
STAMPS = [BASE + timedelta(minutes=5 * i) for i in range(6)]
DT_FROM = datetime(2026, 7, 25, tzinfo=timezone.utc)
DT_TO = datetime(2026, 7, 26, tzinfo=timezone.utc)

# Prose that never names the project: attribution must come from the anchor.
CHAT_TEXT = "Let's fix the thinning in the browser history collector"
SESSION_ID = "session_01DESKTOP"


def write_desktop_code_cache(home: Path, *, repo_slug: str | None) -> None:
    """Seed Claude Desktop's cached /events plus session metadata."""
    cache = home / "Library" / "Application Support" / "Claude" / "Cache" / "Cache_Data"
    cache.mkdir(parents=True, exist_ok=True)

    rows = []
    for index, stamp in enumerate(STAMPS):
        row = {
            "uuid": f"{SESSION_ID}-ev-{index}",
            "session_id": SESSION_ID,
            "type": "user" if index % 2 == 0 else "assistant",
            "created_at": stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "message": {"content": CHAT_TEXT},
        }
        if index == 0:
            # Deliberately an absolute path outside the repo — that is the
            # property under test, so the slug must come from metadata. Kept
            # under /tmp rather than a /Users/<name> home so the fixture carries
            # no shape resembling a real operator's path.
            row["cwd"] = "/tmp/sandbox/worktree"
        rows.append(row)
    (cache / "ev_0").write_bytes(
        _make_entry(
            f"1/0/https://claude.ai/v1/sessions/{SESSION_ID}/events?limit=500",
            json.dumps({"data": rows, "has_more": False}).encode("utf-8"),
        )
    )

    meta: dict = {"id": SESSION_ID, "title": "Fix the thinning"}
    if repo_slug:
        meta["session_context"] = {
            "outcomes": [
                {"type": "git_repository", "git_info": {"repo": repo_slug, "type": "github"}}
            ]
        }
    (cache / "meta_0").write_bytes(
        _make_entry(
            f"1/0/https://claude.ai/v1/sessions/{SESSION_ID}",
            json.dumps(meta).encode("utf-8"),
        )
    )


def write_claude_code_transcript(home: Path) -> None:
    proj = home / ".claude" / "projects" / "-Users-op-work-timelog-extract"
    proj.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "timestamp": stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "type": "user",
                "message": {"content": CHAT_TEXT},
            }
        )
        for stamp in STAMPS
    ]
    (proj / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


class CaptureSourcesRegistryTests(unittest.TestCase):
    def test_registry_lists_both_anchored_surfaces(self):
        self.assertEqual(
            CAPTURE_SOURCES,
            {"claude-code": "Claude Code CLI", "desktop-code": "Claude Desktop (Code)"},
        )

    def test_plain_desktop_chat_is_not_captured(self):
        """It has no anchor, so it would mostly add Uncategorized hours."""
        self.assertNotIn("desktop", CAPTURE_SOURCES)


class DesktopCodeCaptureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.store = self.tmp / "store"

    def tearDown(self):
        self._tmp.cleanup()

    def _capture(self, **kwargs):
        return capture_device_evidence(
            PROFILES,
            DT_FROM,
            DT_TO,
            home=self.home,
            base_dir=self.store,
            device="laptop",
            **kwargs,
        )

    def _records(self):
        return [rec for _month, rec in read_records(events_dir(self.store))]

    def test_desktop_code_session_is_captured(self):
        write_desktop_code_cache(self.home, repo_slug="owner-a/timelog-extract")
        summary = self._capture()
        self.assertGreater(summary["appended"], 0)
        self.assertEqual(summary["sources"], ["desktop-code"])

    def test_repo_anchor_survives_capture_even_with_a_sandbox_cwd(self):
        """The measured property: metadata slug beats an unhelpful cwd."""
        write_desktop_code_cache(self.home, repo_slug="owner-a/timelog-extract")
        summary = self._capture()
        self.assertEqual(summary["projects"], ["gittan"])
        for record in self._records():
            self.assertEqual(record["project_at_capture"], "gittan")
            self.assertEqual(record["source"], "Claude Desktop (Code)")
            self.assertEqual(record["source_provenance"]["captured_via"], "desktop-code")
            self.assertEqual(record["source_provenance"]["device"], "laptop")

    def test_without_git_metadata_hours_are_kept_but_unattributed(self):
        """Honest about the limit: no anchor means the review queue, not silence."""
        write_desktop_code_cache(self.home, repo_slug=None)
        summary = self._capture()
        self.assertGreater(summary["appended"], 0, "hours must not be dropped")
        self.assertEqual(summary["projects"], ["Uncategorized"])

    def test_both_sources_capture_in_one_run(self):
        write_desktop_code_cache(self.home, repo_slug="owner-a/timelog-extract")
        write_claude_code_transcript(self.home)
        summary = self._capture()
        self.assertEqual(summary["sources"], ["claude-code", "desktop-code"])
        sources = {rec["source"] for rec in self._records()}
        self.assertEqual(sources, {"Claude Code CLI", "Claude Desktop (Code)"})

    def test_source_selection_limits_the_run(self):
        write_desktop_code_cache(self.home, repo_slug="owner-a/timelog-extract")
        write_claude_code_transcript(self.home)
        summary = self._capture(sources=["desktop-code"])
        self.assertEqual(summary["sources"], ["desktop-code"])

    def test_capture_is_idempotent_across_sources(self):
        write_desktop_code_cache(self.home, repo_slug="owner-a/timelog-extract")
        write_claude_code_transcript(self.home)
        first = self._capture()
        second = self._capture()
        self.assertEqual(second["appended"], 0)
        self.assertEqual(second["skipped"], first["appended"])

    def test_no_desktop_cache_is_not_an_error(self):
        write_claude_code_transcript(self.home)
        summary = self._capture()
        self.assertEqual(summary["sources"], ["claude-code"])


if __name__ == "__main__":
    unittest.main()
