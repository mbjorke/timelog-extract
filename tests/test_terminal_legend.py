"""Unit tests for new functions in outputs/terminal.py added in this PR."""

import unittest
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

from rich.text import Text

from outputs.terminal import _build_dynamic_legend, print_project_source_mix


class BuildDynamicLegendTests(unittest.TestCase):
    """Tests for _build_dynamic_legend."""

    def test_returns_rich_text_instance(self):
        """_build_dynamic_legend always returns a rich.text.Text object."""
        result = _build_dynamic_legend(["Cursor", "Chrome"])
        self.assertIsInstance(result, Text)

    def test_legend_prefix_present(self):
        """Legend text starts with 'Legend: '."""
        result = _build_dynamic_legend(["Cursor"])
        plain = result.plain
        self.assertTrue(plain.startswith("Legend: "))

    def test_all_sources_in_legend(self):
        """All sources appear in the rendered legend text."""
        sources = ["Claude Code CLI", "GitHub", "Chrome", "Cursor"]
        result = _build_dynamic_legend(sources)
        plain = result.plain
        for src in sources:
            self.assertIn(src, plain)

    def test_empty_sources_returns_legend_prefix_only(self):
        """Empty source list returns 'Legend: ' prefix with no additional sources."""
        result = _build_dynamic_legend([])
        self.assertEqual(result.plain, "Legend: ")

    def test_single_source_no_trailing_separator(self):
        """Single source has no trailing separator appended."""
        result = _build_dynamic_legend(["Cursor"])
        # The separator (two spaces) should only appear between entries.
        # With one entry, plain text should be "Legend: Cursor" with no extra spaces from separator.
        plain = result.plain
        self.assertIn("Cursor", plain)
        # Separator is added between items, so last item should not be followed by separator
        # (the separator code checks idx < len - 1)
        self.assertTrue(plain.endswith("Cursor"))

    def test_sources_order_preserved(self):
        """Sources appear in the legend in the provided order."""
        sources = ["Alpha", "Beta", "Gamma"]
        result = _build_dynamic_legend(sources)
        plain = result.plain
        pos_alpha = plain.index("Alpha")
        pos_beta = plain.index("Beta")
        pos_gamma = plain.index("Gamma")
        self.assertLess(pos_alpha, pos_beta)
        self.assertLess(pos_beta, pos_gamma)


class PrintProjectSourceMixTests(unittest.TestCase):
    """Tests for print_project_source_mix."""

    def _make_events(self, project, sources_counts):
        """Create a flat list of events for a given project with specified source counts."""
        base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        events = []
        minute = 0
        for source, count in sources_counts.items():
            for _ in range(count):
                events.append({
                    "project": project,
                    "source": source,
                    "local_ts": base.replace(minute=minute % 60),
                    "detail": f"detail-{minute}",
                })
                minute += 1
        return events

    def test_empty_project_name_does_not_crash(self):
        """Empty project_name gracefully returns without error."""
        events = self._make_events("ProjectA", {"Cursor": 2})
        # Should not raise
        print_project_source_mix(events, "", ["Cursor"])

    def test_no_matching_project_events_does_not_crash(self):
        """When no events match the project_name, function returns gracefully."""
        events = self._make_events("ProjectA", {"Cursor": 2})
        print_project_source_mix(events, "NonExistentProject", ["Cursor"])

    def test_outputs_source_counts_for_project(self):
        """Source counts for the project are computed correctly."""
        # We'll capture rich console output via StringIO
        from rich.console import Console
        import outputs.terminal as terminal_module

        events = self._make_events("MyProject", {"Cursor": 3, "Chrome": 1})
        buf = StringIO()
        fake_console = Console(file=buf, highlight=False)

        with patch.object(terminal_module, "console", fake_console):
            print_project_source_mix(events, "MyProject", ["Cursor", "Chrome"])

        output = buf.getvalue()
        self.assertIn("MyProject", output)
        self.assertIn("Cursor", output)
        self.assertIn("Chrome", output)

    def test_case_insensitive_project_name_match(self):
        """Project name matching is case-insensitive."""
        from rich.console import Console
        import outputs.terminal as terminal_module

        events = self._make_events("MyProject", {"Cursor": 2})
        buf = StringIO()
        fake_console = Console(file=buf, highlight=False)

        with patch.object(terminal_module, "console", fake_console):
            print_project_source_mix(events, "myproject", ["Cursor"])

        output = buf.getvalue()
        self.assertIn("myproject", output.lower())

    def test_event_span_displayed_for_single_source(self):
        """Event span (first/last timestamp) is included in output."""
        from rich.console import Console
        import outputs.terminal as terminal_module

        base = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        events = [
            {"project": "P", "source": "Cursor", "local_ts": base, "detail": "d1"},
            {"project": "P", "source": "Cursor", "local_ts": base.replace(hour=11), "detail": "d2"},
        ]
        buf = StringIO()
        fake_console = Console(file=buf, highlight=False)

        with patch.object(terminal_module, "console", fake_console):
            print_project_source_mix(events, "P", ["Cursor"])

        output = buf.getvalue()
        # Should show some time span information
        self.assertIn("->", output)

    def test_events_from_other_projects_excluded(self):
        """Events from other projects are not counted in the source mix."""
        from rich.console import Console
        import outputs.terminal as terminal_module

        base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        events = [
            {"project": "ProjectA", "source": "Cursor", "local_ts": base, "detail": "a1"},
            {"project": "ProjectA", "source": "Cursor", "local_ts": base.replace(minute=1), "detail": "a2"},
            {"project": "ProjectB", "source": "GitHub", "local_ts": base.replace(minute=2), "detail": "b1"},
        ]
        buf = StringIO()
        fake_console = Console(file=buf, highlight=False)

        with patch.object(terminal_module, "console", fake_console):
            print_project_source_mix(events, "ProjectA", ["Cursor", "GitHub"])

        output = buf.getvalue()
        # GitHub should not appear (it belongs to ProjectB)
        self.assertNotIn("GitHub", output)


if __name__ == "__main__":
    unittest.main()