"""GH-527: a report attributes unmapped repositories without configuration.

Each test maps to a scenario in
``docs/task-prompts/zero-config-project-attribution-task.md``.
"""

import unittest

from core.derived_attribution import (
    DERIVED_KEY,
    apply_derived_attribution,
    derived_projects,
    derived_slug,
)

UNCATEGORIZED = "Uncategorized"


def event(project, **anchors):
    row = {"source": "Claude Code CLI", "detail": "work", "project": project}
    if anchors:
        row["anchors"] = anchors
    return row


class DerivedAttributionTests(unittest.TestCase):
    def test_derived_attribution_replaces_uncategorized(self):
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, repo="owner/widgets")], uncategorized=UNCATEGORIZED
        )
        self.assertEqual(out[0]["project"], "owner/widgets")
        self.assertIs(out[0][DERIVED_KEY], True)

    def test_a_declared_profile_always_wins(self):
        out = apply_derived_attribution(
            [event("Widgets", repo="owner/widgets")], uncategorized=UNCATEGORIZED
        )
        self.assertEqual(out[0]["project"], "Widgets")
        self.assertNotIn(DERIVED_KEY, out[0])

    def test_signals_that_cannot_carry_identity_stay_out(self):
        # A branch, a session title and a working directory are not durable
        # identities. None of them may create a project row.
        rows = [
            event(UNCATEGORIZED, branch="feature/x"),
            event(UNCATEGORIZED, session="abc123"),
            event(UNCATEGORIZED, dir="briox-buddy"),
            event(UNCATEGORIZED, label="Some session title"),
        ]
        out = apply_derived_attribution(rows, uncategorized=UNCATEGORIZED)
        for row in out:
            self.assertEqual(row["project"], UNCATEGORIZED)
            self.assertNotIn(DERIVED_KEY, row)

    def test_a_bare_leaf_in_the_repo_anchor_is_rejected(self):
        # Not repaired into an identity: a leaf with no owner collides across
        # machines, which is the whole reason remotes are the only source here.
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, repo="widgets")], uncategorized=UNCATEGORIZED
        )
        self.assertEqual(out[0]["project"], UNCATEGORIZED)

    def test_a_worktree_path_never_becomes_a_project(self):
        # The cold-start run surfaced 'framer-gittan-source-f9f98e' as a project.
        # A worktree directory is a branch of one repo, never a repo of its own.
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, dir="framer-gittan-source-f9f98e")],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(out[0]["project"], UNCATEGORIZED)

    def test_slugs_are_normalised_to_lowercase(self):
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, repo="MBjorke/Timelog-Extract")],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(out[0]["project"], "mbjorke/timelog-extract")

    def test_a_nested_path_shaped_anchor_is_rejected(self):
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, repo="host/owner/widgets")], uncategorized=UNCATEGORIZED
        )
        self.assertEqual(out[0]["project"], UNCATEGORIZED)

    def test_the_input_events_are_left_untouched(self):
        # A caller that keeps the raw events must still be able to see what
        # classification alone produced.
        rows = [event(UNCATEGORIZED, repo="owner/widgets")]
        apply_derived_attribution(rows, uncategorized=UNCATEGORIZED)
        self.assertEqual(rows[0]["project"], UNCATEGORIZED)
        self.assertNotIn(DERIVED_KEY, rows[0])

    def test_three_repositories_produce_three_attributed_rows(self):
        rows = [
            event(UNCATEGORIZED, repo="owner/one"),
            event(UNCATEGORIZED, repo="owner/two"),
            event(UNCATEGORIZED, repo="owner/three"),
        ]
        out = apply_derived_attribution(rows, uncategorized=UNCATEGORIZED)
        self.assertEqual(
            {r["project"] for r in out}, {"owner/one", "owner/two", "owner/three"}
        )
        self.assertEqual(len(derived_projects(out)), 3)

    def test_derived_projects_names_only_the_derived_rows(self):
        rows = [
            event("Widgets", repo="owner/widgets"),
            event(UNCATEGORIZED, repo="owner/other"),
            event(UNCATEGORIZED),
        ]
        out = apply_derived_attribution(rows, uncategorized=UNCATEGORIZED)
        self.assertEqual(derived_projects(out), {"owner/other"})

    def test_non_dict_rows_survive_untouched(self):
        out = apply_derived_attribution([None, "junk"], uncategorized=UNCATEGORIZED)
        self.assertEqual(out, [None, "junk"])

    def test_derived_slug_reads_the_repo_anchor(self):
        self.assertEqual(derived_slug(event(UNCATEGORIZED, repo="a/b")), "a/b")
        self.assertEqual(derived_slug(event(UNCATEGORIZED)), "")
        self.assertEqual(derived_slug(None), "")


if __name__ == "__main__":
    unittest.main()


class PayloadContractTests(unittest.TestCase):
    """The payload must make derived rows impossible to mistake for declared."""

    def test_the_payload_version_names_the_new_block(self):
        from core.truth_payload import TRUTH_PAYLOAD_VERSION

        self.assertEqual(TRUTH_PAYLOAD_VERSION, "3")

    def test_derived_names_reach_the_payload_block(self):
        rows = apply_derived_attribution(
            [
                event(UNCATEGORIZED, repo="owner/widgets"),
                event("Declared", repo="owner/declared"),
            ],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(derived_projects(rows), {"owner/widgets"})
        # The declared row must not appear, or a consumer would refuse to bill
        # hours the operator did declare.
        self.assertNotIn("Declared", derived_projects(rows))
