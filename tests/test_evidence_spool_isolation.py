"""The spool drained must belong to the store being written to.

capture_events() deletes every spool file it successfully reads. If the spool
is resolved from the ambient home while events are written to an isolated
base_dir, a caller with a temporary store consumes the real user's pending
commit events and then removes them — the events vanish with the temp dir.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.evidence_store import capture_events, spool_dir, spool_dir_for_base


def _write_spool(spool: Path, name: str, detail: str) -> Path:
    spool.mkdir(parents=True, exist_ok=True)
    path = spool / name
    path.write_text(
        json.dumps({
            "source": "git-commit",
            "timestamp": "2026-08-05T04:00:00+00:00",
            "detail": detail,
            "project": "project-alpha",
        }),
        encoding="utf-8",
    )
    return path


class SpoolRootAgreementTests(unittest.TestCase):
    def test_spool_is_a_sibling_of_evidence_under_every_mode(self):
        """The derivation only holds because the two dirs share a root."""
        from core.evidence_store import evidence_base_dir

        home = Path("/tmp/example-home")
        self.assertEqual(spool_dir_for_base(evidence_base_dir(home)), spool_dir(home))

    def test_derives_from_base_not_from_ambient_home(self):
        base = Path("/tmp/isolated-store/evidence")
        self.assertEqual(spool_dir_for_base(base), Path("/tmp/isolated-store/spool"))


class IsolatedBaseDirTests(unittest.TestCase):
    def test_isolated_base_dir_does_not_drain_the_ambient_spool(self):
        with TemporaryDirectory() as real_home_s, TemporaryDirectory() as isolated_s:
            real_home = Path(real_home_s)
            # GITTAN_HOME is what the ambient resolution actually reads, so this
            # stands in for the maintainer's live store.
            pending = _write_spool(
                real_home / "spool",
                "commit-real.json",
                "[repo:main] a real pending commit",
            )
            isolated_base = Path(isolated_s) / "evidence"

            # base_dir without home — the shape the finding is about.
            with patch.dict(os.environ, {"GITTAN_HOME": str(real_home)}):
                capture_events([], base_dir=isolated_base)

            self.assertTrue(
                pending.exists(),
                "the ambient spool must be untouched when writing to an isolated store",
            )
            written = list((isolated_base / "events").glob("*.jsonl")) if (isolated_base / "events").is_dir() else []
            self.assertEqual(written, [], "the ambient event must not land in the isolated store")

    def test_isolated_base_dir_drains_its_own_spool(self):
        """Isolation must not mean "never drains" — the sibling spool still works."""
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            base = root / "evidence"
            pending = _write_spool(root / "spool", "commit-own.json", "[repo:main] own commit")

            result = capture_events([], base_dir=base)

            self.assertFalse(pending.exists(), "its own spool file should be consumed")
            self.assertGreaterEqual(result.get("appended", 0), 1)

    def test_home_only_path_is_unchanged(self):
        """The common case must behave exactly as before."""
        with TemporaryDirectory() as home_s:
            home = Path(home_s)
            pending = _write_spool(home / ".gittan" / "spool", "commit-h.json", "[repo:main] home commit")

            result = capture_events([], home=home)

            self.assertFalse(pending.exists())
            self.assertGreaterEqual(result.get("appended", 0), 1)


if __name__ == "__main__":
    unittest.main()


class MalformedSpoolFileTests(unittest.TestCase):
    """json.load() accepts values that are not events; they must not linger.

    `[]`, `null` and bare scalars parse cleanly, so the old `if isinstance(ev,
    dict)` branch neither drained nor removed them — every later capture
    rescanned the same file, forever.
    """

    def _drain(self, payload: str) -> bool:
        """Return whether the spool file survived the drain."""
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            spool = root / "spool"
            spool.mkdir(parents=True)
            path = spool / "commit-bad.json"
            path.write_text(payload, encoding="utf-8")
            capture_events([], base_dir=root / "evidence")
            return path.exists()

    def test_json_array_is_removed(self):
        self.assertFalse(self._drain("[]"), "a parseable non-event must not be left behind")

    def test_json_null_is_removed(self):
        self.assertFalse(self._drain("null"))

    def test_bare_scalar_is_removed(self):
        self.assertFalse(self._drain("42"))

    def test_unparseable_json_is_still_removed(self):
        """The pre-existing behaviour must not regress while widening the rule."""
        self.assertFalse(self._drain("{ not json"))
