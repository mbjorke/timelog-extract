"""Tests for interactive mapping review prompts."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.mapping_review import prompt_new_project_fields


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

    def test_cancelling_customer_prompt_is_distinguishable_from_validation_failure(self):
        """Ctrl+C must not look like "slug already mapped" to the caller.

        Both used to return None, so run_batch_mapping_review's `continue`
        carried the user straight to the next proposal after they quit.
        """
        from rich.console import Console

        from core.mapping_review import CANCELLED

        with patch("questionary.text") as text_mock:
            text_mock.return_value.ask.return_value = None
            fields = prompt_new_project_fields(
                Console(),
                default_profile_name="project-alpha",
                existing_names={"project-beta"},
            )
        self.assertIs(fields, CANCELLED)
        self.assertIsNotNone(fields, "cancellation must not collapse into the None case")

    def test_cancelling_title_prompt_also_signals_cancellation(self):
        from rich.console import Console

        from core.mapping_review import CANCELLED

        with patch("questionary.text") as text_mock:
            text_mock.return_value.ask.side_effect = ["customer-a", None]
            fields = prompt_new_project_fields(
                Console(),
                default_profile_name="project-alpha",
                existing_names={"project-beta"},
            )
        self.assertIs(fields, CANCELLED)


if __name__ == "__main__":
    unittest.main()
