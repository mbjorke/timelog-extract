from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rich.console import Console

from core.setup_project_identity_wizard import run_project_identity_wizard


class SetupProjectIdentityWizardTests(unittest.TestCase):
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
            ) as select_mock:
                text_mock.return_value.ask.return_value = "Atlas Studio"
                select_mock.return_value.ask.side_effect = [
                    "Continue",
                    "Continue",
                    "Atlas Studio",
                ]
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
            ) as select_mock:
                text_mock.return_value.ask.return_value = "Atlas Studio"
                # 1) continue step 2) confirm customer list 3) project->customer 4) save
                select_mock.return_value.ask.side_effect = ["Continue", "Continue", "Atlas Studio", "Save"]

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
            ) as select_mock:
                text_prompt = mock.Mock()
                text_prompt.ask.side_effect = [
                    "customer-a.test",
                    "customer-a.test, customer-b.test",
                ]
                text_mock.return_value = text_prompt
                select_mock.return_value.ask.side_effect = [
                    "Continue",  # run step
                    "Continue",  # confirm initial customer list
                    "customer-a.test",  # project 1 selection
                    "Edit customer list...",  # project 2: edit customers
                    "Continue",  # confirm edited customer list
                    "Previous project",  # resume mapping position
                    "customer-b.test",  # project 1 re-selection
                    "customer-a.test",  # project 2 remains on its intended customer
                    "Save",  # save changes
                ]

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

