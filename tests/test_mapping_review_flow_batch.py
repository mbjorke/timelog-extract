"""Tests for interactive duplicate/new-repo mapping review choices."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.mapping_review import (
    MappingReview,
    NewProjectProposal,
    ProjectChangeProposal,
    RepoDuplicateLine,
    slug_to_github_url,
)
from core.mapping_review_flow import (
    _ACTION_CONSOLIDATE,
    _ACTION_MAP_EXISTING,
    run_batch_mapping_review,
)


class RunBatchMappingReviewTests(unittest.TestCase):
    def _profiles(self):
        return [
            {
                "name": "project-alpha",
                "customer": "customer-a.example",
                "match_terms": ["owner-a/project-alpha"],
            },
            {
                "name": "project-alpha-dev",
                "customer": "customer-a.example",
                "match_terms": ["project-alpha-dev"],
            },
        ]

    def _duplicate_review(self) -> MappingReview:
        change = ProjectChangeProposal(
            target_project="project-alpha",
            customer="customer-a.example",
            canonical_slug="owner-a/project-alpha",
            canonical_remote_url=slug_to_github_url("owner-a/project-alpha"),
            canonical_local_path="~/project-alpha",
            canonical_activity_dot="[green]●[/green]",
            lines=[
                RepoDuplicateLine(
                    slug="owner-a/project-alpha-dev-31e799cf",
                    remote_url=slug_to_github_url("owner-a/project-alpha-dev-31e799cf"),
                    local_path="~/project-alpha-dev",
                    activity_dot="[green]●[/green]",
                    status="Primary — remote activity in window",
                ),
            ],
        )
        return MappingReview(changes=[change])

    def _fake_select(self, answers):
        answers = list(answers)
        obj = MagicMock()

        def ask(**kwargs):
            if answers:
                return answers.pop(0)
            return None

        obj.ask.side_effect = ask
        return obj

    def _fake_confirm(self, answer):
        obj = MagicMock()
        obj.ask.return_value = answer
        return obj

    def _select_side_effect(self, responses):
        calls: list[int] = []

        def side_effect(*_args, **_kwargs):
            idx = len(calls)
            calls.append(idx)
            answer = responses[idx] if idx < len(responses) else None
            return self._fake_select([answer])

        return side_effect

    @patch("core.mapping_assistant.apply_mapping_changes", return_value=2)
    @patch("questionary.select")
    def test_duplicate_defaults_to_map_existing(self, select_mock, apply_mock):
        select_mock.side_effect = self._select_side_effect(
            [_ACTION_MAP_EXISTING, "project-alpha-dev"]
        )
        console = MagicMock()
        result = run_batch_mapping_review(
            console,
            self._duplicate_review(),
            self._profiles(),
            "/tmp/projects.json",
        )
        self.assertEqual(result, 2)
        _console, additions, removals, _path = apply_mock.call_args[0]
        self.assertEqual(removals, [])
        values = [value for _p, _t, value in additions]
        self.assertIn("owner-a/project-alpha-dev-31e799cf", values)

    @patch("core.mapping_assistant.apply_mapping_changes", return_value=1)
    @patch("questionary.confirm")
    @patch("questionary.select")
    def test_new_repo_defaults_to_map_existing_when_match(self, select_mock, confirm_mock, apply_mock):
        review = MappingReview(
            new_projects=[
                NewProjectProposal(
                    slug="owner-a/project-alpha-dev-31e799cf",
                    url=slug_to_github_url("owner-a/project-alpha-dev-31e799cf"),
                    created_at=None,
                    suggested_name="project-alpha-dev-31e799cf",
                    local_path="~/project-alpha-dev",
                    activity_dot="[green]●[/green]",
                )
            ]
        )
        select_mock.side_effect = self._select_side_effect(
            [_ACTION_MAP_EXISTING, "project-alpha-dev"]
        )
        confirm_mock.return_value = self._fake_confirm(True)
        console = MagicMock()
        result = run_batch_mapping_review(console, review, self._profiles(), "/tmp/projects.json")
        self.assertEqual(result, 1)
        first_call = select_mock.call_args_list[0]
        self.assertEqual(first_call.kwargs.get("default"), _ACTION_MAP_EXISTING)

    @patch("core.mapping_assistant.apply_mapping_changes", return_value=3)
    @patch("questionary.confirm")
    @patch("questionary.select")
    def test_consolidate_requires_confirm(self, select_mock, confirm_mock, apply_mock):
        select_mock.side_effect = self._select_side_effect([_ACTION_CONSOLIDATE])
        confirm_mock.return_value = self._fake_confirm(False)
        console = MagicMock()
        result = run_batch_mapping_review(
            console,
            self._duplicate_review(),
            self._profiles(),
            "/tmp/projects.json",
        )
        self.assertEqual(result, 0)
        apply_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
