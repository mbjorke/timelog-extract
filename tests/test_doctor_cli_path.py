"""Tests for doctor CLI PATH / install-shadow helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.doctor_cli_path import add_cli_path_rows, list_gittan_on_path


class ListGittanOnPathTests(unittest.TestCase):
    def test_lists_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"
            b = Path(tmp) / "b"
            a.mkdir()
            b.mkdir()
            (a / "gittan").write_text("#!/bin/sh\n", encoding="utf-8")
            (b / "gittan").write_text("#!/bin/sh\n", encoding="utf-8")
            (a / "gittan").chmod(0o755)
            (b / "gittan").chmod(0o755)
            found = list_gittan_on_path(f"{a}{os.pathsep}{b}{os.pathsep}{a}")
            self.assertEqual([p.parent.name for p in found], ["a", "b"])


class AddCliPathRowsShadowTests(unittest.TestCase):
    def test_warns_when_path_shadows_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            running = home / "fresh" / "gittan"
            shadow = home / "old" / "gittan"
            running.parent.mkdir()
            shadow.parent.mkdir()
            running.write_text("#!/bin/sh\n", encoding="utf-8")
            shadow.write_text("#!/bin/sh\n", encoding="utf-8")
            running.chmod(0o755)
            shadow.chmod(0o755)
            calls: list[tuple] = []

            class _FakeTable:
                def add_row(self, *args):
                    calls.append(args)

            with (
                mock.patch("core.doctor_cli_path._running_gittan", return_value=running),
                mock.patch("core.doctor_cli_path.shutil.which", return_value=str(shadow)),
                mock.patch(
                    "core.doctor_cli_path.list_gittan_on_path",
                    return_value=[shadow, running],
                ),
            ):
                ok = add_cli_path_rows(_FakeTable(), home=home)  # type: ignore[arg-type]
            self.assertFalse(ok)
            self.assertEqual(len(calls), 1)
            self.assertIn("gittan.sh/install", calls[0][2])
            self.assertIn(str(shadow), calls[0][2])


if __name__ == "__main__":
    unittest.main()
