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
        with mock.patch("core.setup_project_identity_batch.questionary.select") as select_mock:
            select_mock.return_value.ask.return_value = "__finish_mapping__"
            _collect_batch_mappings(
                Console(record=True),
                projects=[],
                candidates=["project-a"],
                customers=["zeta.test", "Alpha.test", "beta.test"],
            )

        first_choices = select_mock.call_args_list[0].kwargs["choices"]
        first_titles = [choice.title for choice in first_choices]
        first_values = [choice.value for choice in first_choices]
        self.assertEqual(first_titles[:3], ["Alpha.test", "beta.test", "zeta.test"])
        self.assertEqual(
            first_titles[3:],
            [
                "Create new customer...",
                "Edit customer list...",
                "Skip selected projects...",
                "Finish mapping",
                "Cancel setup",
            ],
        )
        self.assertEqual(
            first_values[3:],
            [
                ("action", "create_customer"),
                ("action", "edit_customers"),
                ("action", "skip_projects"),
                ("action", "finish_mapping"),
                ("action", "cancel_setup"),
            ],
        )

    def test_checkbox_choices_are_sorted_case_insensitive(self):
        with mock.patch("core.setup_project_identity_batch.questionary.select") as select_mock, mock.patch(
            "core.setup_project_identity_batch.questionary.checkbox"
        ) as checkbox_mock:
            select_mock.return_value.ask.side_effect = [
                "customer-a.test",
                "__finish_mapping__",
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
            {"name": "customer-a.test", "customer": "customer-a.test", "default_client": ""},
            {"name": "customer-a", "customer": "customer-a", "default_client": ""},
            {"name": "customer-b.test", "customer": "customer-b.test", "default_client": ""},
            {"name": "customer-b", "customer": "customer-b", "default_client": ""},
        ]
        # If all rows are placeholders (customer=name), _existing_customers falls back
        # to listing existing customer values (deduped).
        self.assertEqual(_existing_customers(projects), ["customer-a.test", "customer-b.test"])

        projects2 = [
            {"name": "customer-a", "customer": "customer-a.test", "default_client": ""},
            # Use a non-placeholder row for the "customer-b" group so it is included
            # in the curated path (customer!=name).
            {"name": "customer-b", "customer": "customer-b.test", "default_client": ""},
        ]
        customers = _existing_customers(projects2)
        # Dedup collapses common variants for customer-a and customer-b.
        self.assertEqual(customers, ["customer-a.test", "customer-b.test"])

    def test_batch_mapping_assigns_selected_projects(self):
        with mock.patch("core.setup_project_identity_batch.questionary.select") as select_mock, mock.patch(
            "core.setup_project_identity_batch.questionary.checkbox"
        ) as checkbox_mock:
            select_mock.return_value.ask.side_effect = [
                "customer-a.test",
                "__finish_mapping__",
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
        with mock.patch("core.setup_project_identity_batch.questionary.select") as select_mock, mock.patch(
            "core.setup_project_identity_batch.questionary.text"
        ) as text_mock, mock.patch("core.setup_project_identity_batch.questionary.checkbox") as checkbox_mock:
            select_mock.return_value.ask.side_effect = [
                "__create_customer__",
                "__finish_mapping__",
            ]
            text_mock.return_value.ask.return_value = "customer-b"
            checkbox_mock.return_value.ask.return_value = ["project-a"]
            _customers, assignments = _collect_batch_mappings(
                Console(record=True),
                projects=[],
                candidates=["project-a"],
                customers=["customer-b.test"],
            )

        self.assertEqual(assignments["project-a"], "customer-b.test")

    def test_batch_map_offers_stem_match_not_unrelated(self):
        from core.setup_project_identity_candidates import batch_choices_for_customer

        projects = [
            {
                "name": "customer-a",
                "customer": "customer-a.test",
                "default_client": "customer-a.test",
            },
            {"name": "project-beta", "customer": "", "default_client": ""},
            {"name": "project-gamma", "customer": "", "default_client": ""},
        ]
        choices, suggested, already = batch_choices_for_customer(
            projects,
            customer="customer-a.test",
            unresolved=["project-beta", "project-gamma"],
        )
        self.assertEqual(already, ["customer-a"])
        self.assertEqual(suggested, [])
        self.assertEqual(choices, ["customer-a"])
        self.assertNotIn("project-beta", choices)

    def test_batch_map_suggests_unlinked_stem_match(self):
        from core.setup_project_identity_candidates import batch_choices_for_customer

        projects = [
            {"name": "customer-a", "customer": "", "default_client": ""},
            {"name": "project-beta", "customer": "", "default_client": ""},
        ]
        choices, suggested, already = batch_choices_for_customer(
            projects,
            customer="customer-a.test",
            unresolved=["customer-a", "project-beta"],
        )
        self.assertEqual(already, [])
        self.assertEqual(suggested, ["customer-a"])
        self.assertEqual(choices, ["customer-a"])

    def test_batch_map_includes_wrongly_linked_stem_match(self):
        from core.setup_project_identity_candidates import batch_choices_for_customer

        projects = [
            {
                "name": "customer-a",
                "customer": "other.test",
                "default_client": "other.test",
            },
            {"name": "project-beta", "customer": "", "default_client": ""},
        ]
        # Not in unresolved pool (looks "resolved"), but stem-matches customer-a.test.
        choices, suggested, already = batch_choices_for_customer(
            projects,
            customer="customer-a.test",
            unresolved=["project-beta"],
        )
        self.assertEqual(already, [])
        self.assertEqual(suggested, ["customer-a"])
        self.assertEqual(choices, ["customer-a"])

    def test_shared_github_owner_does_not_inflate_all_customer_rows(self):
        from core.setup_project_identity_candidates import _customer_candidate_rows

        projects = [
            {
                "name": "project-alpha",
                "customer": "customer-a.test",
                "match_terms": ["owner-a/project-alpha", "owner-shared/tool-repo"],
            },
            {
                "name": "project-beta",
                "customer": "customer-b.test",
                "match_terms": ["owner-shared/tool-repo", "owner-shared/other-repo"],
            },
            {
                "name": "project-gamma",
                "customer": "operator-name",
                "match_terms": ["owner-shared/tool-repo"],
            },
        ]
        with mock.patch(
            "core.setup_project_identity_candidates._local_owner_activity_summary",
            return_value=(
                {"owner-shared": 29, "owner-a": 1},
                {"owner-shared": "owner-shared/tool-repo", "owner-a": "owner-a/project-alpha"},
                {
                    "owner-shared": [(100, "owner-shared/tool-repo"), (90, "owner-shared/other-repo")],
                    "owner-a": [(80, "owner-a/project-alpha")],
                },
            ),
        ), mock.patch(
            "core.setup_project_identity_candidates.discover_git_project_hints",
            return_value=None,
        ):
            rows = _customer_candidate_rows(
                projects,
                ["customer-a.test", "customer-b.test", "operator-name"],
            )
        by_customer = {row[0]: row for row in rows}
        # Shared personal owner must not copy a 29-repo wall onto every customer.
        self.assertEqual(by_customer["customer-b.test"][1], "2")
        self.assertEqual(by_customer["operator-name"][1], "1")
        self.assertNotEqual(by_customer["customer-b.test"][1], "29")
        self.assertIn("owner-a/project-alpha", by_customer["customer-a.test"][3])

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

            projects_payload = json.loads(cfg.read_text(encoding="utf-8"))["projects"]

            def _reload_projects(_console, *, config_path, dry_run):
                return projects_payload

            with mock.patch(
                "core.setup_project_identity_wizard.reload_projects_after_evidence_mapping",
                side_effect=_reload_projects,
            ), mock.patch("core.setup_project_identity_wizard.questionary.text") as text_mock, mock.patch(
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

            projects_payload = json.loads(cfg.read_text(encoding="utf-8"))["projects"]

            def _reload_projects(_console, *, config_path, dry_run):
                return projects_payload

            with mock.patch(
                "core.setup_project_identity_wizard.reload_projects_after_evidence_mapping",
                side_effect=_reload_projects,
            ), mock.patch("core.setup_project_identity_wizard.questionary.text") as text_mock, mock.patch(
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

            projects_payload = json.loads(cfg.read_text(encoding="utf-8"))["projects"]

            def _reload_projects(_console, *, config_path, dry_run):
                return projects_payload

            with mock.patch(
                "core.setup_project_identity_wizard.reload_projects_after_evidence_mapping",
                side_effect=_reload_projects,
            ), mock.patch("core.setup_project_identity_wizard.questionary.text") as text_mock, mock.patch(
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
                    "__edit_customers__",  # edit customers
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

