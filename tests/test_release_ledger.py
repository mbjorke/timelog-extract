"""Tests for the release-ledger generator.

The git-dependent parts are exercised through a stubbed ``_git`` so the suite
does not depend on the checkout's tags or depth — which is exactly the fragility
the generator itself refuses to paper over (``git_can_answer``).
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_release_ledger.py"
_spec = importlib.util.spec_from_file_location("generate_release_ledger", _SCRIPT)
rl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rl)


def _release(version, date, stories=()):
    return rl.Release(version, date, set(stories))


class ChangelogParsingTests(unittest.TestCase):
    def test_reads_dated_sections_and_skips_undated_ones(self):
        text = (
            "# Changelog\n\n"
            "## Unreleased\n\n- something pending\n\n"
            "## 0.5.0 - 2026-08-23\n\n- Feat (GH-527): thing\n- Fix (GH-448)\n\n"
            "## 0.4.2 - 2026-08-10\n\n- Fix: other\n"
        )
        with mock.patch.object(rl, "CHANGELOG_PATH") as path:
            path.read_text.return_value = text
            releases = rl.changelog_releases()
        self.assertEqual([r.version for r in releases], ["0.5.0", "0.4.2"])
        self.assertEqual(releases[0].story_ids, {"527", "448"})
        self.assertEqual(releases[1].story_ids, set())


class TagParsingTests(unittest.TestCase):
    def test_only_strict_semver_counts_as_a_release_tag(self):
        with mock.patch.object(
            rl, "_git", return_value="v0.4.2\nv0.5.0\nv0.2.5rc1-Claude-version\n"
        ):
            tags, other = rl.release_tags()
        self.assertEqual(tags, {"0.4.2": "v0.4.2", "0.5.0": "v0.5.0"})
        self.assertEqual(other, ["v0.2.5rc1-Claude-version"])


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.releases = [
            _release("0.5.0", "2026-08-23"),
            _release("0.4.2", "2026-08-10"),
            _release("0.4.1", "2026-08-07"),
            _release("0.4.0", "2026-08-07"),
        ]

    def test_tagged_release_ends_at_its_own_tag(self):
        tags = {"0.5.0": "v0.5.0", "0.4.2": "v0.4.2", "0.4.0": "v0.4.0"}
        start, end, tagged = rl._range_for(self.releases[0], 0, self.releases, tags)
        self.assertEqual((start, end, tagged), ("v0.4.2", "v0.5.0", True))

    def test_untagged_latest_runs_to_the_default_branch_not_head(self):
        tags = {"0.4.2": "v0.4.2", "0.4.0": "v0.4.0"}
        with mock.patch.object(rl, "open_end_ref", return_value="origin/main"):
            start, end, tagged = rl._range_for(self.releases[0], 0, self.releases, tags)
        self.assertEqual((start, end, tagged), ("v0.4.2", "origin/main", False))

    def test_untagged_historical_release_is_bounded_by_the_next_newer_tag(self):
        """A 2026-08-07 release must not be handed every commit since."""
        tags = {"0.5.0": "v0.5.0", "0.4.2": "v0.4.2", "0.4.0": "v0.4.0"}
        start, end, tagged = rl._range_for(self.releases[2], 2, self.releases, tags)
        self.assertEqual((start, end, tagged), ("v0.4.0", "v0.4.2", False))


class SpecMatchingTests(unittest.TestCase):
    def test_matches_on_changelog_story_id_or_on_a_pr_in_range(self):
        refs = [
            rl.SpecRef("docs/specs/a.md", "built", {"527"}, set()),
            rl.SpecRef("docs/specs/b.md", "partial", set(), {"575"}),
            rl.SpecRef("docs/specs/c.md", "", {"999"}, {"111"}),
        ]
        matched = rl.specs_for_release(_release("0.5.0", "d", {"527"}), {"575"}, refs)
        self.assertEqual([r.path for r in matched], ["docs/specs/a.md", "docs/specs/b.md"])


class NeedsAttentionTests(unittest.TestCase):
    """The one untagged version that is still fixable must not be buried."""

    def test_separates_the_current_untagged_line_from_dead_history(self):
        releases = [
            _release("0.5.0", "2026-08-23"),
            _release("0.4.2", "2026-08-10"),
            _release("0.2.9", "2026-04-16"),
        ]
        tags = {"0.4.2": "v0.4.2"}
        with mock.patch.multiple(
            rl,
            changelog_releases=mock.Mock(return_value=releases),
            release_tags=mock.Mock(return_value=(tags, [])),
            load_spec_refs=mock.Mock(return_value=[]),
            commits_between=mock.Mock(return_value=[]),
            open_end_ref=mock.Mock(return_value="origin/main"),
            project_version=mock.Mock(return_value="0.5.0"),
        ):
            report = rl.build_report()
        self.assertIn("**`0.5.0` is written but never released.**", report)
        self.assertIn("`pyproject.toml` declares `0.5.0`", report)
        # The dead one is summarized, never given its own alarm line.
        self.assertIn("1 older version(s) were never tagged", report)
        self.assertNotIn("**`0.2.9` is written but never released.**", report)


class ShallowCloneTests(unittest.TestCase):
    def test_refuses_to_report_from_a_shallow_clone(self):
        with mock.patch.object(rl, "_git", return_value="true"):
            self.assertFalse(rl.git_can_answer())


if __name__ == "__main__":
    unittest.main()
