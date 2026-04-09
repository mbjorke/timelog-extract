"""Regression: AGENTS.md must keep TIMELOG clock-time policy (see docs/incidents/)."""

from pathlib import Path
import unittest


def _agents_text() -> str:
    root = Path(__file__).resolve().parent.parent
    path = root / "AGENTS.md"
    return path.read_text(encoding="utf-8")


class AgentsTimelogPolicyTests(unittest.TestCase):
    """Ensures TIMELOG timestamp rules are not accidentally removed from AGENTS.md."""

    def test_agents_md_exists(self):
        root = Path(__file__).resolve().parent.parent
        self.assertTrue((root / "AGENTS.md").is_file())

    def test_requires_real_wall_clock_language(self):
        text = _agents_text()
        self.assertIn("Clock time must be real local wall time", text)

    def test_requires_date_command_example(self):
        text = _agents_text()
        self.assertIn("date '+%Y-%m-%d %H:%M'", text)

    def test_forbids_placeholder_times_example(self):
        text = _agents_text()
        self.assertIn("18:00", text)
        self.assertIn("placeholder", text.lower())

    def test_requires_ask_if_time_unknown(self):
        text = _agents_text()
        self.assertIn("ask the user", text.lower())


if __name__ == "__main__":
    unittest.main()
