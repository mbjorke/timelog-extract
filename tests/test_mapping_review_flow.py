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


if __name__ == "__main__":
    unittest.main()
