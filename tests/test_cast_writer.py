from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app
from outputs.cast_writer import CastWriter


def _read_cast(path: Path) -> tuple[dict, list[list]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[0]), [json.loads(line) for line in lines[1:]]


class CastWriterTests(unittest.TestCase):
    def test_writer_uses_presentation_timing_and_fallback_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo.cast"
            writer = CastWriter(out, event_step=0.5)

            writer.bee_box("Gittan Status", ["Local traces become review-ready evidence."])
            writer.table(
                cols=[
                    {"label": "Project", "align": "left"},
                    {"label": "Hours", "align": "right"},
                ],
                rows=[
                    {"cells": ["Gittan", "2.5h"]},
                    {"cells": ["Total", "2.5h"], "total": True},
                ],
            )
            writer.pause(2.0)
            writer.status_line("observed → classified → approved")
            writer.note("nothing is billable until approval.")
            writer.save()

            raw_text = out.read_text(encoding="utf-8")
            header, events = _read_cast(out)
            semantic = [event for event in events if event[1] == "g"]
            fallback = [event for event in events if event[1] == "o"]

            self.assertEqual(header["version"], 3)
            self.assertEqual(header["duration"], 3.5)
            self.assertEqual([event[0] for event in semantic], [0.0, 0.5, 3.0, 3.5])
            self.assertIn("observed → classified → approved", raw_text)
            self.assertNotIn("\\u2192", raw_text)
            self.assertEqual(len(fallback), 4)
            self.assertIn("  __   Gittan Status", fallback[0][2])
            self.assertIn("Project  Hours", fallback[1][2])
            self.assertIn("Gittan    2.5h", fallback[1][2])
            self.assertEqual(writer.event_count, 4)

    def test_health_table_writes_plain_terminal_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "doctor.cast"
            writer = CastWriter(out)
            writer.health_table([
                {"source": "Chrome History", "status": "ok", "detail": "DB query successful"},
                {"source": "Toggl Source", "status": "warn", "detail": "Not configured"},
            ])
            writer.save()

            _header, events = _read_cast(out)
            fallback = [event for event in events if event[1] == "o"]

            self.assertEqual(len(fallback), 1)
            self.assertIn("Source / Path", fallback[0][2])
            self.assertIn("Chrome History", fallback[0][2])
            self.assertIn("Toggl Source", fallback[0][2])


class CastCommandTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_cast_command_writes_semantic_and_fallback_events(self):
        def fake_status(writer: CastWriter, **_kwargs):
            writer.prompt("gittan status --today")
            writer.bee_box("Gittan Status", ["Local traces become review-ready evidence."])
            writer.table(
                cols=[
                    {"label": "Project", "align": "left"},
                    {"label": "Hours", "align": "right"},
                    {"label": "Sessions", "align": "right"},
                ],
                rows=[
                    {"cells": ["timelog-extract", "1.0h", "2"]},
                    {"cells": ["Total", "1.0h", "2"], "total": True},
                ],
            )

        def fake_doctor(writer: CastWriter):
            writer.prompt("gittan doctor")
            writer.health_table([
                {"source": "CLI (gittan on PATH)", "status": "ok", "detail": "/tmp/gittan"},
            ])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.cast"
            with patch("core.cli_cast._record_status", side_effect=fake_status), patch(
                "core.cli_cast._record_doctor",
                side_effect=fake_doctor,
            ):
                result = self.runner.invoke(app, ["cast", "--today", "--out", str(out)])

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("semantic events", result.output)

            header, events = _read_cast(out)
            semantic = [event for event in events if event[1] == "g"]
            fallback = [event for event in events if event[1] == "o"]

            self.assertEqual(header["title"], "gittan demo")
            self.assertGreater(header["duration"], 0)
            self.assertGreaterEqual(len(semantic), 6)
            self.assertGreaterEqual(len(fallback), 4)
            self.assertEqual(semantic[0][2]["t"], "prompt")
            self.assertEqual(semantic[1][2]["t"], "bee-box")
            self.assertIn("timelog-extract", "\n".join(event[2] for event in fallback))


if __name__ == "__main__":
    unittest.main()
