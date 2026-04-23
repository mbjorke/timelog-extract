"""Tests for new terminal output functions: _build_dynamic_legend, print_project_source_mix."""

import io
import unittest
from datetime import datetime, timezone

from rich.console import Console
from rich.text import Text

from outputs.terminal import _build_dynamic_legend, print_project_source_mix


def _make_event(source, project, detail, minute=0):
    ts = datetime(2026, 4, 10, 10, minute, tzinfo=timezone.utc)
    return {
        "source": source,
        "project": project,
        "detail": detail,
        "local_ts": ts,
    }


class BuildDynamicLegendTests(unittest.TestCase):
    """Tests for _build_dynamic_legend()."""

    def test_returns_text_instance(self):
        result = _build_dynamic_legend(["Claude", "GitHub"])
        self.assertIsInstance(result, Text)

    def test_legend_label_present(self):
        result = _build_dynamic_legend(["Cursor"])
        plain = result.plain
        self.assertIn("Legend:", plain)

    def test_all_sources_appear_in_legend(self):
        sources = ["Claude", "Cursor", "GitHub", "Chrome"]
        result = _build_dynamic_legend(sources)
        plain = result.plain
        for source in sources:
            self.assertIn(source, plain, f"Expected {source!r} in legend plain text")

    def test_empty_source_list_produces_legend_label_only(self):
        result = _build_dynamic_legend([])
        plain = result.plain
        self.assertIn("Legend:", plain)

    def test_single_source_no_separator_after(self):
        """Only one source — no trailing separator."""
        result = _build_dynamic_legend(["Cursor"])
        plain = result.plain
        # Strip the "Legend: " prefix and check it's just the source name
        after_label = plain.replace("Legend: ", "")
        self.assertNotIn("  ", after_label.rstrip())

    def test_multiple_sources_have_spacing(self):
        """Multiple sources should have spaces between them in plain text."""
        result = _build_dynamic_legend(["A", "B", "C"])
        plain = result.plain
        # The separator is two spaces ("  "), ensure total length increases
        self.assertGreater(len(plain), len("Legend: ABC"))

    def test_legend_order_matches_source_order(self):
        sources = ["First", "Second", "Third"]
        result = _build_dynamic_legend(sources)
        plain = result.plain
        # Verify ordering by checking index positions
        idx_first = plain.index("First")
        idx_second = plain.index("Second")
        idx_third = plain.index("Third")
        self.assertLess(idx_first, idx_second)
        self.assertLess(idx_second, idx_third)


class PrintProjectSourceMixTests(unittest.TestCase):
    """Tests for print_project_source_mix() using a captured Rich console."""

    def _capture_output(self, func, *args, **kwargs):
        """Run func with outputs captured via a Rich Console writing to StringIO."""
        buf = io.StringIO()
        test_console = Console(file=buf, highlight=False, markup=False)
        import unittest.mock as mock
        with mock.patch("outputs.terminal.console", test_console):
            func(*args, **kwargs)
        return buf.getvalue()

    def test_empty_project_name_produces_no_output(self):
        events = [_make_event("Cursor", "ProjectA", "some work")]
        output = self._capture_output(
            print_project_source_mix, events, "", ["Cursor"]
        )
        self.assertEqual(output, "")

    def test_no_matching_events_produces_no_output(self):
        events = [_make_event("Cursor", "ProjectA", "some work")]
        output = self._capture_output(
            print_project_source_mix, events, "ProjectB", ["Cursor"]
        )
        self.assertEqual(output, "")

    def test_matching_events_show_project_name(self):
        events = [_make_event("Cursor", "MyProject", "coding work")]
        output = self._capture_output(
            print_project_source_mix, events, "MyProject", ["Cursor"]
        )
        self.assertIn("MyProject", output)

    def test_source_counts_appear_in_output(self):
        events = [
            _make_event("Cursor", "MyProject", "edit 1", minute=0),
            _make_event("Cursor", "MyProject", "edit 2", minute=5),
            _make_event("GitHub", "MyProject", "push", minute=10),
        ]
        output = self._capture_output(
            print_project_source_mix, events, "MyProject", ["Cursor", "GitHub"]
        )
        self.assertIn("Cursor", output)
        self.assertIn("GitHub", output)

    def test_event_span_time_appears_in_output(self):
        events = [
            _make_event("Cursor", "MyProject", "edit", minute=0),
            _make_event("Cursor", "MyProject", "edit", minute=30),
        ]
        output = self._capture_output(
            print_project_source_mix, events, "MyProject", ["Cursor"]
        )
        # Should mention start and end times
        self.assertIn("->", output)

    def test_case_insensitive_project_match(self):
        """Project matching should be case-insensitive."""
        events = [_make_event("Cursor", "myproject", "work")]
        output = self._capture_output(
            print_project_source_mix, events, "MyProject", ["Cursor"]
        )
        # Should match despite case difference
        self.assertIn("MyProject", output)

    def test_event_count_in_output(self):
        events = [
            _make_event("Cursor", "MyProject", "e1", minute=0),
            _make_event("Cursor", "MyProject", "e2", minute=1),
            _make_event("Cursor", "MyProject", "e3", minute=2),
        ]
        output = self._capture_output(
            print_project_source_mix, events, "MyProject", ["Cursor"]
        )
        self.assertIn("3", output)

    def test_empty_events_list_produces_no_output(self):
        output = self._capture_output(
            print_project_source_mix, [], "MyProject", ["Cursor"]
        )
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()