"""Tests for activity-anchor value rules and unmapped-anchor aggregation."""

import unittest

from core.projects_audit import (
    aggregate_top_anchors,
    is_junk_anchor_value,
    is_value_anchored_by_profiles,
    unanchored_top_anchors,
)


class AnchorValueTests(unittest.TestCase):
    def test_junk_anchor_values_rejected(self) -> None:
        # Tool plumbing never qualifies as a project mapping suggestion.
        self.assertTrue(is_junk_anchor_value(".claude"))
        self.assertTrue(is_junk_anchor_value(".git"))
        self.assertTrue(is_junk_anchor_value(".gittan:"))
        self.assertTrue(is_junk_anchor_value("a5cda8b561bb6536e880481734199a568cb647f4"))
        self.assertTrue(is_junk_anchor_value(""))
        # Real project anchors pass.
        self.assertFalse(is_junk_anchor_value("timelog-extract"))
        self.assertFalse(is_junk_anchor_value("project-beta-dashboard"))
        # A <slug>-<hex> suffix is NOT junk: Lovable renames repos with a hex
        # suffix (financing-portal-dev-31e799cf), indistinguishable at the leaf
        # level from a Claude worktree slug. Worktree leakage is handled at the
        # path/remote layer, not here.
        self.assertFalse(is_junk_anchor_value("financing-portal-dev-31e799cf"))
        self.assertFalse(is_junk_anchor_value("offer-craft-34"))

    def test_is_value_anchored_substring_rule(self) -> None:
        profiles = [{"name": "p", "match_terms": ["timelog-extract"], "tracked_urls": []}]
        self.assertTrue(is_value_anchored_by_profiles("timelog-extract", profiles))
        self.assertTrue(is_value_anchored_by_profiles("timelog-extract-dashboard", profiles))
        self.assertFalse(is_value_anchored_by_profiles("unrelated-repo", profiles))

    def test_aggregate_top_anchors_counts_once_per_event(self) -> None:
        events = [
            {"anchors": {"dir": "Repo-One"}},
            {"anchors": {"dir": "repo-one"}},
            {"anchors": {"dir": "repo-two"}},
            {"anchors": {"branch": "repo-one"}},
            {"detail": "no dir"},
        ]
        rows = dict(aggregate_top_anchors(events, "dir", limit=10))
        # case-insensitive aggregation collapses to a single lowercase key
        self.assertEqual(rows.get("repo-one"), 2)
        self.assertEqual(rows.get("repo-two"), 1)
        # A different kind is counted separately.
        self.assertEqual(dict(aggregate_top_anchors(events, "branch", limit=10)).get("repo-one"), 1)


class UnanchoredTopAnchorsTests(unittest.TestCase):
    def test_mapped_repo_slug_covers_worktree_leaves(self) -> None:
        # A worktree event carries both the per-worktree dir leaf and the
        # worktree-invariant repo slug. Once the slug is in match_terms, the
        # dir/branch leaves must stop nagging: the work is attributed.
        events = [
            {
                "source": "Claude Code CLI",
                "detail": "x",
                "anchors": {
                    "repo": "owner-a/project-alpha",
                    "dir": "confident-hopper-fe58c2",
                    "branch": "confident-hopper",
                },
            }
        ] * 3
        profiles = [{"name": "alpha", "match_terms": ["owner-a/project-alpha"]}]
        self.assertEqual(unanchored_top_anchors(events, profiles, min_hits=1), [])
        # Without the slug mapped, only the repo anchor surfaces: the dir/branch
        # leaves are ephemeral worktree noise, so the user maps the repo, never
        # the worktree name.
        rows = unanchored_top_anchors(events, [], min_hits=1)
        kinds = {row["kind"] for row in rows}
        self.assertEqual(kinds, {"repo"})

    def test_dir_branch_surface_only_without_a_repo_anchor(self) -> None:
        # Non-git activity (no repo anchor) still surfaces its dir/branch leaves.
        events = [
            {"source": "Cursor", "detail": "x", "anchors": {"dir": "some-project"}},
            {"source": "Cursor", "detail": "x", "anchors": {"dir": "some-project"}},
        ]
        rows = unanchored_top_anchors(events, [], min_hits=1)
        self.assertEqual([(r["kind"], r["value"]) for r in rows], [("dir", "some-project")])

    def test_unanchored_top_anchors_skips_junk_values(self) -> None:
        events = [
            {"source": "Cursor", "detail": "x", "anchors": {"dir": ".claude"}},
            {"source": "Cursor", "detail": "x", "anchors": {"dir": ".claude"}},
            {"source": "Cursor", "detail": "x", "anchors": {"dir": "project-gamma"}},
        ]
        out = unanchored_top_anchors(events, [], min_hits=1)
        values = [row["value"] for row in out]
        self.assertNotIn(".claude", values)
        self.assertIn("project-gamma", values)


if __name__ == "__main__":
    unittest.main()
