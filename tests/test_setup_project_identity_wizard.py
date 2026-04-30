from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rich.console import Console

from core.setup_project_identity_wizard import (
    _candidate_projects_for_customer_mapping,
    _collect_batch_mappings,
    _existing_customers,
    run_project_identity_wizard,
)


class SetupProjectIdentityWizardTests(unittest.TestCase):
    def test_candidate_projects_are_sorted_case_insensitive(self):
        projects = [
            {"name": "zeta-app", "customer": "", "default_client": ""},
            {"name": "Alpha-service", "customer": "Alpha-service", "default_client": ""},
            {"name": "beta-core", "customer": "beta-customer", "default_client": ""},
        ]

        result = _candidate_projects_for_customer_mapping(projects)
        self.assertEqual(result, ["Alpha-service", "beta-core", "zeta-app"])

    def test_customer_select_choices_are_sorted_before_special_actions(self):
        with mock.patch("core.setup_project_identity_wizard.questionary.select") as select_mock:
            select_mock.return_value.ask.return_value = "Finish mapping"
            _collect_batch_mappings(
                Console(record=True),
                projects=[],
                candidates=["project-a"],
                customers=["zeta.test", "Alpha.test", "beta.test"],
            )

        first_choices = select_mock.call_args_list[0].kwargs["choices"]
        self.assertEqual(first_choices[:3], ["Alpha.test", "beta.test", "zeta.test"])
        self.assertEqual(
            first_choices[3:],
            [
                "Create new customer...",
                "Edit customer list...",
                "Skip selected projects...",
                "Finish mapping",
                "Cancel setup",
            ],
        )

    def test_checkbox_choices_are_sorted_case_insensitive(self):
        with mock.patch("core.setup_project_identity_wizard.questionary.select") as select_mock, mock.patch(
            "core.setup_project_identity_wizard.questionary.checkbox"
        ) as checkbox_mock:
            # choose customer, checkbox selection applies immediately, then finish loop
            select_mock.return_value.ask.side_effect = [
                "customer-a.test",
                "Finish mapping",
            ]
            checkbox_mock.return_value.ask.return_value = ["beta-project"]
            _collect_batch_mappings(
                Console(record=True),
                projects=[],
                candidates=["zeta-project", "Alpha-project", "beta-project"],
                customers=["customer-a.test"],
            )

        self.assertEqual(
            checkbox_mock.call_args_list[0].kwargs["choices"],
            ["Alpha-project", "beta-project", "zeta-project"],
        )

    def test_existing_customers_dedupes_common_variants(self):
        projects = [
            {"name": "AX Finans", "customer": "AX Finans", "default_client": ""},
            {"name": "ax-finans", "customer": "ax-finans", "default_client": ""},
            {"name": "blueberry.ax", "customer": "blueberry.ax", "default_client": ""},
            {"name": "Blueberry", "customer": "Blueberry", "default_client": ""},
        ]
        # If all rows are placeholders (customer=name), _existing_customers falls back
        # to listing existing customer values (deduped).
        self.assertEqual(_existing_customers(projects), ["AX Finans", "blueberry.ax"])

        projects2 = [
            {"name": "ax-finans", "customer": "AX Finans", "default_client": ""},
            # Use a non-placeholder row for the "blueberry" group so it is included
            # in the curated path (customer!=name).
            {"name": "Blueberry", "customer": "blueberry.ax", "default_client": ""},
        ]
        customers = _existing_customers(projects2)
        # Dedup collapses "Blueberry" + "blueberry.ax" and casing variants.
        self.assertEqual(customers, ["AX Finans", "blueberry.ax"])

    def test_batch_mapping_assigns_selected_projects(self):
        with mock.patch("core.setup_project_identity_wizard.questionary.select") as select_mock, mock.patch(
            "core.setup_project_identity_wizard.questionary.checkbox"
        ) as checkbox_mock:
            select_mock.return_value.ask.side_effect = [
                "customer-a.test",
                "Finish mapping",
            ]
            checkbox_mock.return_value.ask.return_value = ["project-beta", "project-gamma"]

            _, assignments = _collect_batch_mappings(
                Console(record=True),
                projects=[],
                candidates=["project-alpha", "project-beta", "project-gamma"],
                customers=["customer-a.test"],
            )

        self.assertEqual(assignments["project-beta"], "customer-a.test")
        self.assertEqual(assignments["project-gamma"], "customer-a.test")
        self.assertNotIn("project-alpha", assignments)

    def test_create_new_customer_reuses_normalized_existing_customer(self):
        with mock.patch("core.setup_project_identity_wizard.questionary.select") as select_mock, mock.patch(
            "core.setup_project_identity_wizard.questionary.text"
        ) as text_mock, mock.patch("core.setup_project_identity_wizard.questionary.checkbox") as checkbox_mock:
            select_mock.return_value.ask.side_effect = [
                "Create new customer...",
                "Finish mapping",
            ]
            text_mock.return_value.ask.return_value = "Blueberry"
            checkbox_mock.return_value.ask.return_value = ["project-a"]
            _customers, assignments = _collect_batch_mappings(
                Console(record=True),
                projects=[],
                candidates=["project-a"],
                customers=["blueberry.ax"],
            )

        self.assertEqual(assignments["project-a"], "blueberry.ax")

    def test_dry_run_does_not_write_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "worklog": "TIMELOG.md",
                        "projects": [
                            {
                                "name": "northwind-web",
                                "customer": "northwind-web",
                                "match_terms": ["northwind-web"],
                                "tracked_urls": [],
                            },
                            {
                                "name": "atlas-site",
                                "customer": "Atlas Studio",
                                "default_client": "Atlas Studio",
                                "match_terms": ["atlas-site"],
                                "tracked_urls": [],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            before = cfg.read_text(encoding="utf-8")

            with mock.patch("core.setup_project_identity_wizard.questionary.text") as text_mock, mock.patch(
                "core.setup_project_identity_wizard.questionary.select"
            ) as select_mock, mock.patch("core.setup_project_identity_wizard.questionary.checkbox") as checkbox_mock:
                text_mock.return_value.ask.return_value = "Atlas Studio"
                select_mock.return_value.ask.side_effect = [
                    "Continue",
                    "Continue",
                    "Atlas Studio",
                ]
                checkbox_mock.return_value.ask.return_value = ["northwind-web"]
                run_project_identity_wizard(Console(record=True), config_path=cfg, dry_run=True)

            self.assertEqual(cfg.read_text(encoding="utf-8"), before)

    def test_save_updates_customer_fields_but_not_match_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "worklog": "TIMELOG.md",
                        "projects": [
                            {
                                "name": "northwind-web",
                                "customer": "northwind-web",
                                "default_client": "northwind-web",
                                "project_id": "",
                                "canonical_project": "",
                                "match_terms": ["northwind-web"],
                                "tracked_urls": [],
                            },
                            {
                                "name": "atlas-site",
                                "customer": "Atlas Studio",
                                "default_client": "Atlas Studio",
                                "project_id": "atlas-site",
                                "canonical_project": "atlas-site",
                                "match_terms": ["atlas-site"],
                                "tracked_urls": [],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("core.setup_project_identity_wizard.questionary.text") as text_mock, mock.patch(
                "core.setup_project_identity_wizard.questionary.select"
            ) as select_mock, mock.patch("core.setup_project_identity_wizard.questionary.checkbox") as checkbox_mock:
                text_mock.return_value.ask.return_value = "Atlas Studio"
                # 1) continue step 2) confirm customer list 3) batch customer 4) save
                select_mock.return_value.ask.side_effect = [
                    "Continue",
                    "Continue",
                    "Atlas Studio",
                    "Save",
                ]
                checkbox_mock.return_value.ask.return_value = ["northwind-web"]

                run_project_identity_wizard(Console(record=True), config_path=cfg, dry_run=False)

            payload = json.loads(cfg.read_text(encoding="utf-8"))
            proj = payload["projects"][0]
            self.assertEqual(proj["customer"], "Atlas Studio")
            self.assertEqual(proj["default_client"], "northwind-web")
            self.assertTrue(proj["project_id"])
            self.assertTrue(proj["canonical_project"])
            # Conservative: do not invent match_terms
            self.assertEqual(proj["match_terms"], ["northwind-web"])

    def test_cancel_setup_raises_keyboard_interrupt_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "worklog": "TIMELOG.md",
                        "projects": [
                            {
                                "name": "northwind-web",
                                "customer": "northwind-web",
                                "match_terms": ["northwind-web"],
                                "tracked_urls": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            before = cfg.read_text(encoding="utf-8")

            with mock.patch("core.setup_project_identity_wizard.questionary.select") as select_mock:
                select_mock.return_value.ask.return_value = "Cancel setup"
                with self.assertRaises(KeyboardInterrupt):
                    run_project_identity_wizard(Console(record=True), config_path=cfg, dry_run=False)

            self.assertEqual(cfg.read_text(encoding="utf-8"), before)

    def test_edit_customer_list_is_safe_and_project_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps(
                    {
                        "worklog": "TIMELOG.md",
                        "projects": [
                            {
                                "name": "project-alpha",
                                "customer": "project-alpha",
                                "match_terms": ["project-alpha"],
                                "tracked_urls": [],
                            },
                            {
                                "name": "project-beta",
                                "customer": "project-beta",
                                "match_terms": ["project-beta"],
                                "tracked_urls": [],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("core.setup_project_identity_wizard.questionary.text") as text_mock, mock.patch(
                "core.setup_project_identity_wizard.questionary.select"
            ) as select_mock, mock.patch("core.setup_project_identity_wizard.questionary.checkbox") as checkbox_mock:
                text_prompt = mock.Mock()
                text_prompt.ask.side_effect = [
                    "customer-a.test",
                    "customer-a.test, customer-b.test",
                ]
                text_mock.return_value = text_prompt
                select_mock.return_value.ask.side_effect = [
                    "Continue",  # run step
                    "Continue",  # confirm initial customer list
                    "customer-a.test",  # batch map some projects to customer-a
                    "Edit customer list...",  # edit customers
                    "Continue",  # confirm edited customer list
                    "customer-b.test",  # batch map remaining to customer-b
                    "Save",  # save changes
                ]
                checkbox_prompt = mock.Mock()
                checkbox_prompt.ask.side_effect = [
                    ["project-beta"],  # map beta -> customer-a
                    ["project-alpha"],  # map alpha -> customer-b
                ]
                checkbox_mock.return_value = checkbox_prompt

                run_project_identity_wizard(Console(record=True), config_path=cfg, dry_run=False)

            payload = json.loads(cfg.read_text(encoding="utf-8"))
            by_name = {p["name"]: p for p in payload["projects"]}
            self.assertEqual(by_name["project-alpha"]["customer"], "customer-b.test")
            self.assertEqual(by_name["project-beta"]["customer"], "customer-a.test")

            # The edit step should preserve prior list as the default value.
            text_calls = text_mock.call_args_list
            self.assertGreaterEqual(len(text_calls), 2)
            self.assertEqual(text_calls[1].kwargs.get("default"), "customer-a.test")


if __name__ == "__main__":
    unittest.main()

