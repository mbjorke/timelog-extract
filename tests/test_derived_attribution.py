"""GH-527: a report attributes unmapped repositories without configuration.

Each test maps to a scenario in
``docs/task-prompts/zero-config-project-attribution-task.md``.
"""

import unittest

from core.derived_attribution import (
    DERIVED_KEY,
    apply_derived_attribution,
    billing_classes,
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

    def test_the_payload_version_covers_the_new_block(self):
        # `project_attribution` arrived in v3. The exact current version is
        # pinned once, in tests/test_truth_payload.py where the payload lives —
        # pinning it here too would mean two edits for every future bump, and
        # what matters to this feature is only that the payload is new enough.
        from core.truth_payload import TRUTH_PAYLOAD_VERSION

        self.assertGreaterEqual(int(TRUTH_PAYLOAD_VERSION), 3)

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

    def test_a_name_collision_is_refused_rather_than_merged(self):
        # Review found the merge wrong in both directions: treat the row as
        # derived and declared hours lose their billable total; treat it as
        # declared and hours nobody configured get billed. The collision is
        # refused instead, so no row is ever part declared and part derived.
        rows = apply_derived_attribution(
            [
                event("owner-example/widgets", repo="owner-example/widgets"),
                event(UNCATEGORIZED, repo="owner-example/widgets"),
            ],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(
            [r["project"] for r in rows], ["owner-example/widgets", UNCATEGORIZED]
        )
        # Direction one: the declared row is not marked derived, so it keeps
        # its billable total.
        self.assertEqual(derived_projects(rows), set())
        # Direction two: the unclaimed event did not join the billed row.
        self.assertNotIn(DERIVED_KEY, rows[1])

    def test_the_collision_guard_ignores_case(self):
        # A derived slug is lowercased; a profile name is whatever the operator
        # typed. Owner/Repo and owner/repo are one repository, and two rows for
        # it would show the same work twice with different billing on each.
        for declared in ("Owner-Example/Widgets", "OWNER-EXAMPLE/WIDGETS"):
            rows = apply_derived_attribution(
                [
                    event(declared, repo="Owner-Example/Widgets"),
                    event(UNCATEGORIZED, repo="Owner-Example/Widgets"),
                ],
                uncategorized=UNCATEGORIZED,
            )
            self.assertEqual(derived_projects(rows), set(), declared)
            self.assertEqual(
                [r["project"] for r in rows], [declared, UNCATEGORIZED], declared
            )

    def test_a_collision_does_not_stop_other_repositories_deriving(self):
        rows = apply_derived_attribution(
            [
                event("owner-example/widgets", repo="owner-example/widgets"),
                event(UNCATEGORIZED, repo="owner-example/widgets"),
                event(UNCATEGORIZED, repo="owner-example/other"),
            ],
            uncategorized=UNCATEGORIZED,
        )
        self.assertEqual(derived_projects(rows), {"owner-example/other"})

    def test_a_relative_path_never_becomes_a_repository_identity(self):
        # `git clone ../work/clone` leaves an origin shaped exactly like
        # owner/repo, so only the absence of a host can tell them apart.
        from core.repo_slug import slug_from_remote_url

        for path in ("work/clone", "some/dir", "../sibling/repo"):
            self.assertEqual(slug_from_remote_url(path), "", path)

    def test_published_remotes_still_resolve(self):
        # The host rule must not cost any real remote.
        from core.repo_slug import slug_from_remote_url

        for url, expected in (
            ("https://github.com/owner/repo", "owner/repo"),
            ("git@github.com:owner/repo.git", "owner/repo"),
            ("git@gitlab.com:team/tool.git", "team/tool"),
            ("ssh://git@host.example/team/tool.git", "team/tool"),
            ("https://gitlab.example.com/team/tool.git", "team/tool"),
        ):
            self.assertEqual(slug_from_remote_url(url), expected, url)

    def test_a_local_path_never_becomes_a_repository_identity(self):
        # A repository whose origin points at a directory has published nothing.
        # A fabricated slug can collide with a real remote, and lifts a folder
        # name — sometimes a customer's — into a visible project row.
        from core.repo_slug import slug_from_remote_url

        for path in (
            "/home/user/project",
            "/Users/someone/Work/customer-a",
            "file:///home/user/project",
            "file:/home/user/project",
            "FILE:///home/user/project",
            "FiLe://localhost/home/user/project",
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
        # name in the block that resolves to nothing in `projects`. Asserted
        # against a built payload rather than the source text, so a rewrite that
        # keeps the behaviour passes and one that loses it does not.
        from datetime import datetime, timedelta, timezone

        from core.truth_payload import build_truth_payload
        from timelog_extract import estimate_hours_by_day, group_by_day

        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        billed = {
            "source": "TIMELOG.md",
            "timestamp": base,
            "detail": "declared work",
            "project": "project-alpha",
        }
        # Derived, and deliberately absent from project_reports: this is the
        # event that produced a name with no row behind it.
        stray = {
            "source": "Claude Code CLI",
            "timestamp": base,
            "detail": "unclaimed work",
            "project": "owner-example/stray",
            DERIVED_KEY: True,
        }
        grouped = group_by_day([billed])
        overall_days = estimate_hours_by_day(
            grouped, gap_minutes=15, min_session_minutes=15, min_session_passive_minutes=5
        )
        payload = build_truth_payload(
            overall_days=overall_days,
            project_reports={"project-alpha": overall_days},
            included_events=[billed, stray],
            collector_status={"TIMELOG.md": {"enabled": True, "reason": "", "events": 1}},
            screen_time_days=None,
            dt_from=base,
            dt_to=base + timedelta(hours=1),
            worklog_path="/tmp/TIMELOG.md",
            config_path="/tmp/cfg.json",
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            session_duration_hours_fn=(
                lambda ev, start, end, mn, mp: (end - start).total_seconds() / 3600.0
            ),
        )
        derived = payload["project_attribution"]["derived"]
        self.assertNotIn("owner-example/stray", derived)
        for name in derived:
            self.assertIn(name, payload["projects"], name)


class AdditiveBillingTests(unittest.TestCase):
    """Additive mode folds a whole session into its primary project, so one row
    can hold declared and derived hours at once."""

    def _rows(self):
        declared = {"project": "project-alpha", "detail": "a"}
        derived = {"project": "owner-example/widgets", "detail": "b", DERIVED_KEY: True}
        return declared, derived

    def test_a_declared_row_that_absorbed_derived_hours_is_not_billed(self):
        declared, derived = self._rows()
        # Additive puts every event of the session under the primary project.
        by_project = {"project-alpha": [declared, declared, derived]}
        d, mixed = billing_classes(by_project, additive_summary=True)
        self.assertEqual(mixed, {"project-alpha"})
        # It is not called derived, because it is not: the project is declared.
        self.assertNotIn("project-alpha", d)

    def test_a_derived_primary_absorbing_declared_hours_stays_derived(self):
        declared, derived = self._rows()
        by_project = {"owner-example/widgets": [derived, derived, declared]}
        d, mixed = billing_classes(by_project, additive_summary=True)
        self.assertEqual(d, {"owner-example/widgets"})
        self.assertEqual(mixed, set())

    def test_a_clean_additive_row_is_billable(self):
        declared, _ = self._rows()
        d, mixed = billing_classes({"project-alpha": [declared]}, additive_summary=True)
        self.assertEqual((d, mixed), (set(), set()))

    def test_outside_additive_mode_no_row_is_ever_mixed(self):
        declared, derived = self._rows()
        by_project = {
            "project-alpha": [declared],
            "owner-example/widgets": [derived],
        }
        d, mixed = billing_classes(by_project, additive_summary=False)
        self.assertEqual(d, {"owner-example/widgets"})
        self.assertEqual(mixed, set())


if __name__ == "__main__":
    unittest.main()
