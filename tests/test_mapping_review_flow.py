"""Tests for interactive mapping review prompts."""

from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from core.mapping_review import (
    _CANCEL,
    MappingReview,
    NewProjectProposal,
    ProjectChangeProposal,
    prompt_new_project_fields,
    run_batch_mapping_review,
)


class PromptNewProjectFieldsTests(unittest.TestCase):
    def test_uses_repo_slug_and_empty_customer_fields(self):
        from rich.console import Console

        with patch("questionary.text") as text_mock:
            text_mock.return_value.ask.side_effect = [
                "Ålandsbanken Contact Center",
                "Ålandsbanken Maud Johans",
            ]
            fields = prompt_new_project_fields(
                Console(),
                default_profile_name="landsbanken-faq-helper",
                existing_names={"timelog-extract"},
            )
        self.assertEqual(
            fields,
            ("landsbanken-faq-helper", "Ålandsbanken Contact Center", "Ålandsbanken Maud Johans"),
        )
        self.assertEqual(text_mock.call_args_list[0].kwargs.get("default"), "")
        self.assertEqual(text_mock.call_args_list[1].kwargs.get("default"), "")

    def test_rejects_when_repo_slug_already_mapped(self):
        from rich.console import Console

        with patch("questionary.text") as text_mock:
            fields = prompt_new_project_fields(
                Console(),
                default_profile_name="landsbanken-faq-helper",
                existing_names={"landsbanken-faq-helper"},
            )
        self.assertIsNone(fields)
        text_mock.assert_not_called()


def _new_project(slug: str) -> NewProjectProposal:
    name = slug.split("/")[-1]
    return NewProjectProposal(
        slug=slug,
        url=f"https://example.invalid/{slug}",
        created_at=None,
        suggested_name=name,
        local_path=f"/workspace/{name}",
    )


class CancelKeepsCompletedMappingsTests(unittest.TestCase):
    """GH-522: cancel stops the queue; it must not discard completed answers."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_path = Path(self._tmp.name) / "timelog_projects.json"
        self.profiles = [{"name": "example-project", "match_terms": ["example"]}]
        self.config_path.write_text(json.dumps({"projects": self.profiles}), encoding="utf-8")

    def _console(self):
        from rich.console import Console

        buffer = StringIO()
        return Console(file=buffer, width=200, no_color=True), buffer

    def _written_match_terms(self) -> list[str]:
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        for project in payload.get("projects", []):
            if project.get("name") == "example-project":
                return list(project.get("match_terms") or [])
        return []

    def _run_cancel_at_second_prompt(self, cancel_value):
        """Map repo-one to an existing project, then back out on repo-two."""
        console, buffer = self._console()
        review = MappingReview(
            new_projects=[_new_project("acme/repo-one"), _new_project("acme/repo-two")],
        )
        with patch("questionary.select") as select_mock:
            select_mock.return_value.ask.side_effect = [
                "Map to existing project",  # repo-one: how to handle
                "example-project",  # repo-one: map to which project
                cancel_value,  # repo-two: cancel / Ctrl-C
            ]
            applied = run_batch_mapping_review(
                console, review, self.profiles, str(self.config_path)
            )
        return applied, buffer.getvalue()

    def test_menu_cancel_keeps_the_mapping_already_completed(self):
        applied, output = self._run_cancel_at_second_prompt(_CANCEL)

        self.assertEqual(applied, 1)
        self.assertIn("acme/repo-one", self._written_match_terms())
        self.assertNotIn("acme/repo-two", self._written_match_terms())
        self.assertIn("Stopped", output)
        self.assertNotIn("no mapping changes saved", output)

    def test_ctrl_c_keeps_the_mapping_already_completed(self):
        # questionary returns None for a Ctrl-C interrupt: a separate code path
        # from the explicit Cancel choice, so it is proved separately.
        applied, output = self._run_cancel_at_second_prompt(None)

        self.assertEqual(applied, 1)
        self.assertIn("acme/repo-one", self._written_match_terms())
        self.assertNotIn("acme/repo-two", self._written_match_terms())
        self.assertIn("Stopped", output)
        self.assertNotIn("no mapping changes saved", output)

    def test_cancel_before_any_answer_writes_nothing(self):
        console, buffer = self._console()
        review = MappingReview(new_projects=[_new_project("acme/repo-one")])
        with patch("questionary.select") as select_mock:
            select_mock.return_value.ask.side_effect = [_CANCEL]
            applied = run_batch_mapping_review(
                console, review, self.profiles, str(self.config_path)
            )

        self.assertEqual(applied, 0)
        self.assertEqual(self._written_match_terms(), ["example"])
        self.assertIn("no mapping changes saved", buffer.getvalue())

    def test_cancel_stops_the_rest_of_the_queue(self):
        console, _buffer = self._console()
        review = MappingReview(
            new_projects=[_new_project("acme/repo-one")],
            changes=[
                ProjectChangeProposal(
                    target_project="example-project",
                    customer="Example Customer",
                    canonical_slug="acme/example",
                    canonical_remote_url="https://example.invalid/acme/example",
                    canonical_local_path="/workspace/example",
                    canonical_activity_dot="[dim]●[/dim]",
                )
            ],
        )
        with patch("questionary.select") as select_mock:
            select_mock.return_value.ask.side_effect = [_CANCEL]
            applied = run_batch_mapping_review(
                console, review, self.profiles, str(self.config_path)
            )

        self.assertEqual(applied, 0)
        # Cancel means "stop asking": the duplicate-group prompt is never shown.
        self.assertEqual(select_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
