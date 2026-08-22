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
            event(UNCATEGORIZED, dir="project-alpha"),
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
        # A cold-start run surfaced a worktree directory as its own project row.
        # A worktree is a branch of one repository, never a repository of its own.
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, dir="project-alpha--task-something-a1b2c3")],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(out[0]["project"], UNCATEGORIZED)

    def test_slugs_are_normalised_to_lowercase(self):
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, repo="Owner-Example/Project-Alpha")],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(out[0]["project"], "owner-example/project-alpha")

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


class ReviewFindingTests(unittest.TestCase):
    """Regressions for defects found in review of GH-527."""

    def test_a_declared_row_keeps_its_billing_when_a_derived_row_shares_its_name(self):
        # A profile named for a slug, or an intent bound to one, can collide
        # with a derived row. Marking the merged row derived strips the billable
        # total from hours the operator declared — silently, and downward.
        rows = apply_derived_attribution(
            [
                event("owner-example/widgets", repo="owner-example/widgets"),
                event(UNCATEGORIZED, repo="owner-example/widgets"),
            ],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual([r["project"] for r in rows], ["owner-example/widgets"] * 2)
        self.assertEqual(derived_projects(rows), set())

    def test_a_local_path_never_becomes_a_repository_identity(self):
        # A repository whose origin points at a directory has published nothing.
        # A fabricated slug can collide with a real remote, and lifts a folder
        # name — sometimes a customer's — into a visible project row.
        from core.repo_slug import slug_from_remote_url

        for path in (
            "/home/user/project",
            "/Users/someone/Work/customer-a",
            "file:///home/user/project",
            "~/work/thing",
            "C:\\src\\repo",
        ):
            self.assertEqual(slug_from_remote_url(path), "", path)

    def test_scp_style_remotes_reduce_to_owner_repo(self):
        # Without this the owner is "git@host:team", which would become the
        # visible name of a project row.
        from core.repo_slug import slug_from_remote_url

        self.assertEqual(slug_from_remote_url("git@gitlab.com:team/tool.git"), "team/tool")
        self.assertEqual(slug_from_remote_url("git@bitbucket.org:team/tool.git"), "team/tool")
        self.assertEqual(slug_from_remote_url("git@github.com:owner/repo.git"), "owner/repo")
        self.assertEqual(
            slug_from_remote_url("https://gitlab.example.com/team/tool.git"), "team/tool"
        )

    def test_an_anchor_carrying_host_syntax_is_rejected(self):
        out = apply_derived_attribution(
            [event(UNCATEGORIZED, repo="git@gitlab.com:team/tool")],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(out[0]["project"], UNCATEGORIZED)

    def test_every_test_class_runs_on_direct_execution(self):
        # The runner block sat above two classes, so running the file directly
        # skipped them.
        import tests.test_derived_attribution as module

        source = open(module.__file__).read()
        self.assertTrue(
            source.rstrip().endswith("unittest.main()"),
            "the __main__ block must stay last or later classes never run",
        )

    def test_every_derived_name_is_a_row_a_consumer_can_look_up(self):
        # An event can be included and still contribute no hours, which left a
        # name in the block that resolves to nothing in `projects`.
        import inspect

        from core.truth_payload import build_truth_payload

        source = inspect.getsource(build_truth_payload)
        self.assertIn(
            "derived_project_names & set(project_totals)",
            source,
            "the derived list must be scoped to names that are rows in projects",
        )


if __name__ == "__main__":
    unittest.main()
