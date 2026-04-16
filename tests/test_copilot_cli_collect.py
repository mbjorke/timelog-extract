"""Tests for GitHub Copilot CLI log collector."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors import copilot_cli


def _make_event(source, ts, detail, project):
    return {"source": source, "timestamp": ts, "detail": detail, "project": project}


class CopilotCliCollectTests(unittest.TestCase):
    def test_collect_parses_timestamp_in_log(self):
        utc = timezone.utc
        dt_from = datetime(2026, 4, 10, 0, 0, 0, tzinfo=utc)
        dt_to = datetime(2026, 4, 10, 23, 59, 59, 999999, tzinfo=utc)
        line = "2026-04-10T12:00:05Z session start example"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / ".copilot" / "logs"
            root.mkdir(parents=True)
            (root / "process-test.log").write_text(line + "\n", encoding="utf-8")

            def classify(_hay, _profiles):
                return "default-project"

            events = copilot_cli.collect_copilot_cli(
                [],
                dt_from,
                dt_to,
                home,
                classify,
                _make_event,
            )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "GitHub Copilot CLI")
        self.assertEqual(events[0]["project"], "default-project")
        ts = events[0]["timestamp"]
        self.assertEqual(ts.astimezone(utc), datetime(2026, 4, 10, 12, 0, 5, tzinfo=utc))

    def test_collect_empty_when_no_logs_dir(self):
        utc = timezone.utc
        dt_from = datetime(2026, 1, 1, tzinfo=utc)
        dt_to = datetime(2026, 1, 2, tzinfo=utc)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            events = copilot_cli.collect_copilot_cli(
                [],
                dt_from,
                dt_to,
                home,
                lambda _h, _p: "x",
                _make_event,
            )
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
