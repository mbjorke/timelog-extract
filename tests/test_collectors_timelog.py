from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.timelog import collect_worklog


class TimelogCollectorTests(unittest.TestCase):
    def test_worklog_fallback_classification_uses_worklog_path_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "timelog-extract"
            root.mkdir(parents=True, exist_ok=True)
            worklog = root / "TIMELOG.md"
            worklog.write_text(
                "## 2026-05-01 10:00\n- chore: update commit summary\n",
                encoding="utf-8",
            )

            def classify_project(text, _profiles):
                lowered = (text or "").lower()
                if "timelog-extract" in lowered or "timelog.md" in lowered:
                    return "timelog-extract"
                return "Uncategorized"

            out = collect_worklog(
                worklog_path=worklog,
                dt_from=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 5, 1, 23, 59, tzinfo=timezone.utc),
                profiles=[],
                local_tz=timezone.utc,
                classify_project=classify_project,
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                source_name="TIMELOG.md",
                worklog_format="md",
            )

            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["project"], "timelog-extract")
            self.assertIn("chore: update commit summary", out[0]["detail"])

    def test_worklog_gtimelog_format_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worklog = root / "timelog.txt"
            worklog.write_text(
                "2026-05-01 10:00: task-a\n2026-05-01 10:15: task-b\n",
                encoding="utf-8",
            )

            out = collect_worklog(
                worklog_path=worklog,
                dt_from=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
                dt_to=datetime(2026, 5, 1, 23, 59, tzinfo=timezone.utc),
                profiles=[],
                local_tz=timezone.utc,
                classify_project=lambda text, _profs: "Uncategorized",
                make_event=lambda source, ts, detail, project: {
                    "source": source,
                    "timestamp": ts,
                    "detail": detail,
                    "project": project,
                },
                source_name="timelog.txt",
                worklog_format="gtimelog",
            )

            self.assertEqual(len(out), 2)
            self.assertEqual(out[0]["timestamp"], datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc))
            self.assertEqual(out[0]["detail"], "task-a")
            self.assertEqual(out[1]["timestamp"], datetime(2026, 5, 1, 10, 15, tzinfo=timezone.utc))
            self.assertEqual(out[1]["detail"], "task-b")

    def test_parsing_fromisoformat_matches_strptime(self):
        date_str = "2026-07-25"
        time_str = "12:34"

        expected = datetime(2026, 7, 25, 12, 34, tzinfo=timezone.utc)

        parsed_iso = datetime.fromisoformat(f"{date_str} {time_str}:00").replace(tzinfo=timezone.utc)
        parsed_strp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)

        self.assertEqual(parsed_iso, expected)
        self.assertEqual(parsed_iso, parsed_strp)


if __name__ == "__main__":
    unittest.main()
