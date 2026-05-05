from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.timelog import collect_worklog
from core.runtime_collectors import RuntimeCollectors


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

    def test_runtime_collect_worklog_merges_multiple_paths_without_duplicates(self):
        calls = []

        class _FakeTimelogCollector:
            @staticmethod
            def collect_worklog(
                worklog_path,
                dt_from,
                dt_to,
                profiles,
                local_tz,
                classify_project,
                make_event,
                source_name,
                *,
                worklog_format="auto",
            ):
                calls.append(str(worklog_path))
                return [
                    {
                        "source": source_name,
                        "timestamp": dt_from,
                        "detail": "same event",
                        "project": "project-a",
                    }
                ]

        runtime = RuntimeCollectors(
            cli_args=type("Args", (), {"worklog_format": "auto"})(),
            home=Path("."),
            local_tz=timezone.utc,
            chrome_epoch_delta_us=0,
            uncategorized="Uncategorized",
            cursor_checkpoints_dir=Path("."),
            codex_ide_session_index=Path("."),
            worklog_source="TIMELOG.md",
            cursor_checkpoints_source="Cursor checkpoints",
            classify_project_fn=lambda text, _profiles: text,
            make_event_fn=lambda source, ts, detail, project: {
                "source": source,
                "timestamp": ts,
                "detail": detail,
                "project": project,
            },
            ai_logs_collector=object(),
            chrome_collector=object(),
            cursor_collector=object(),
            mail_collector=object(),
            timelog_collector=_FakeTimelogCollector(),
            github_collector=object(),
            toggl_collector=object(),
        )
        dt = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        rows = runtime.collect_worklog(
            ["/tmp/a/TIMELOG.md", "/tmp/b/TIMELOG.md"],
            dt,
            dt,
            profiles=[],
        )
        self.assertEqual(calls, ["/tmp/a/TIMELOG.md", "/tmp/b/TIMELOG.md"])
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
