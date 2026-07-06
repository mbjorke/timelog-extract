"""Regression: AGENTS.md must keep the "never publish real business data" policy."""

import unittest
from pathlib import Path


def _agents_text() -> str:
    root = Path(__file__).resolve().parent.parent
    path = root / "AGENTS.md"
    return path.read_text(encoding="utf-8")


class AgentsBusinessDataPolicyTests(unittest.TestCase):
    """Ensures the real-business-data publication policy stays explicit in AGENTS.md."""

    def test_agents_md_exists(self):
        root = Path(__file__).resolve().parent.parent
        self.assertTrue((root / "AGENTS.md").is_file())

    def test_requires_policy_section_header(self):
        text = _agents_text()
        self.assertIn("## Documentation privacy and path hygiene", text)

    def test_forbids_publishing_real_business_data(self):
        text = _agents_text()
        self.assertIn(
            "Never publish the maintainer's real business data in any GitHub artifact",
            text,
        )

    def test_covers_hours_and_amounts_per_project_or_client(self):
        text = _agents_text()
        self.assertIn("real hours/amounts per project or client", text)

    def test_covers_client_project_names_tied_to_numbers(self):
        text = _agents_text()
        self.assertIn("client/project", text)
        self.assertIn("names tied to those numbers", text)

    def test_covers_invoice_and_ledger_figures(self):
        text = _agents_text()
        self.assertIn("invoice/ledger figures", text)

    def test_covers_live_config_values(self):
        text = _agents_text()
        self.assertIn("live config values", text)
        self.assertIn("match_terms", text)
        self.assertIn("tracked_urls", text)
        self.assertIn("timelog_projects.json", text)

    def test_allows_real_data_validation_in_chat_only(self):
        text = _agents_text()
        self.assertIn("Real-data validation", text)
        self.assertIn(
            "numbers and names stay in chat\nwith the maintainer only", text
        )

    def test_requires_abstract_description_on_github(self):
        text = _agents_text()
        self.assertIn('describe it in the abstract ("shifts small', text)
        self.assertIn(
            "with no figures, client names, or config values", text
        )

    def test_requires_anonymize_or_omit_when_in_doubt(self):
        text = _agents_text()
        self.assertIn("When in doubt, anonymize or omit.", text)

    def test_business_data_policy_precedes_fixture_hygiene_section(self):
        text = _agents_text()
        business_data_idx = text.find(
            "Never publish the maintainer's real business data"
        )
        fixture_hygiene_idx = text.find(
            "## Test and fixture data hygiene (mandatory)"
        )
        self.assertNotEqual(business_data_idx, -1)
        self.assertNotEqual(fixture_hygiene_idx, -1)
        self.assertLess(business_data_idx, fixture_hygiene_idx)


if __name__ == "__main__":
    unittest.main()