"""Tests for `gittan review` create-project + decidability (#419)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core.cli_review_create_project import (
    ReviewCreateProposal,
    create_choice_label,
    decidability_sort_key,
    durable_match_terms_from_url_key,
    is_decidable_candidate,
    park_choice_label,
    partition_candidates,
    propose_create_from_candidate,
    write_created_project,
)
from core.cli_triage_map_candidates import UrlCandidate
from core.cli_url_mapping import _project_choices_for_row


def _row(
    *,
    title: str,
    url_key: str,
    events: int = 3,
    impact_hours: float = 0.0,
    days: int = 1,
    last_seen: str = "2026-07-21",
) -> UrlCandidate:
    return UrlCandidate(
        title=title,
        url_key=url_key,
        suggested_project="Uncategorized",
        confidence_label="low",
        confidence_score=0.0,
        impact_hours=impact_hours,
        events=events,
        days=days,
        last_seen=last_seen,
        sample_urls=[],
    )


class ProposeCreateTests(unittest.TestCase):
    def test_title_and_github_slug_proposes_create(self):
        row = _row(
            title="Project Alpha portal",
            url_key="github.com/acme/project-alpha",
            impact_hours=0.0,
        )
        proposal = propose_create_from_candidate(row)
        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertEqual(proposal.profile_name, "project-alpha")
        self.assertEqual(proposal.tracked_urls, ["github.com/acme/project-alpha"])
        self.assertEqual(proposal.match_terms, ["acme/project-alpha"])
        # Session title must not become a match_term.
        self.assertNotIn("Project Alpha portal", proposal.match_terms)
        self.assertTrue(is_decidable_candidate(row))
        choices = _project_choices_for_row(row, project_names=[])
        self.assertIn(create_choice_label(), choices)
        self.assertNotIn(park_choice_label(), choices)

    def test_human_title_on_lovable_uuid_proposes_create_without_uuid_match_term(self):
        uuid_host = "85f3c1b3-64e9-4296-85f4-10dc31037933.lovableproject.com"
        row = _row(title="Lunch Connect", url_key=uuid_host, events=21, impact_hours=0.0)
        proposal = propose_create_from_candidate(row)
        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertEqual(proposal.profile_name, "lunch-connect")
        self.assertEqual(proposal.tracked_urls, [uuid_host])
        self.assertEqual(proposal.match_terms, ["lunch-connect"])
        self.assertNotIn("Lunch Connect", proposal.match_terms)

    def test_bare_lovable_uuid_does_not_propose_create(self):
        uuid_host = "85f3c1b3-64e9-4296-85f4-10dc31037933.lovableproject.com"
        row = _row(title="Untitled", url_key=uuid_host, events=50, impact_hours=9.9)
        self.assertIsNone(propose_create_from_candidate(row))
        self.assertFalse(is_decidable_candidate(row))
        choices = _project_choices_for_row(row, project_names=["project-alpha"])
        self.assertNotIn(create_choice_label(), choices)
        self.assertIn(park_choice_label(), choices)
        self.assertEqual(durable_match_terms_from_url_key(uuid_host), [])


class RankingAndPartitionTests(unittest.TestCase):
    def test_decidable_impact_zero_kept_and_ranked_above_undecidable(self):
        decidable = _row(
            title="Project Alpha",
            url_key="github.com/acme/project-alpha",
            events=2,
            impact_hours=0.0,
        )
        undecidable = _row(
            title="Untitled",
            url_key="85f3c1b3-64e9-4296-85f4-10dc31037933.lovableproject.com",
            events=99,
            impact_hours=12.0,
        )
        decidable_rows, parked = partition_candidates([undecidable, decidable])
        self.assertEqual([r.url_key for r in decidable_rows], [decidable.url_key])
        self.assertEqual([r.url_key for r in parked], [undecidable.url_key])
        # Sort key prefers decidable even when impact is lower.
        self.assertLess(decidability_sort_key(decidable), decidability_sort_key(undecidable))


class WriteCreatedProjectTests(unittest.TestCase):
    def test_write_creates_profile_tracked_urls_with_backup(self):
        with TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(json.dumps({"projects": []}), encoding="utf-8")
            proposal = ReviewCreateProposal(
                profile_name="project-alpha",
                match_terms=["acme/project-alpha"],
                tracked_urls=["github.com/acme/project-alpha"],
                display_name="Project Alpha",
            )
            fake_backup = Path(tmp) / "timelog_projects.backup.20260723-120000.json"
            with mock.patch(
                "core.cli_review_create_project.backup_projects_config_if_exists",
                return_value=fake_backup,
            ) as backup_mock:
                backup = write_created_project(
                    projects_config=str(cfg),
                    proposal=proposal,
                    customer="Customer A",
                )
            backup_mock.assert_called_once()
            self.assertEqual(backup, fake_backup)
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["projects"]), 1)
            project = payload["projects"][0]
            self.assertEqual(project["name"], "project-alpha")
            self.assertEqual(project["tracked_urls"], ["github.com/acme/project-alpha"])
            self.assertEqual(project["match_terms"], ["acme/project-alpha"])
            self.assertEqual(project["customer"], "Customer A")
            self.assertEqual(project["invoice_title"], "Project Alpha")


if __name__ == "__main__":
    unittest.main()
