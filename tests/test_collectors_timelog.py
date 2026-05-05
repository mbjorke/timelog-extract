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


if __name__ == "__main__":
    unittest.main()
