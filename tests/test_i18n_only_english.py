"""Guardrail: user-facing text should stay only English/ASCII."""

from __future__ import annotations

import unicodedata
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Keep scope tight to user-facing CLI/report surfaces.
TARGETS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "core" / "cli.py",
    REPO_ROOT / "outputs",
]

def _iter_files(path: Path):
    if path.is_file():
        yield path
        return
    for p in path.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".md", ".txt", ".json"}:
            yield p


class I18nOnlyEnglishTests(unittest.TestCase):
    def test_only_ascii_letters_in_user_facing_surfaces(self):
        offenders = []
        for target in TARGETS:
            for file_path in _iter_files(target):
                text = file_path.read_text(encoding="utf-8")
                for idx, ch in enumerate(text):
                    # Allow punctuation symbols (em dash, box drawing, etc.),
                    # but reject non-ASCII letters from other languages.
                    if ord(ch) > 127 and unicodedata.category(ch).startswith("L"):
                        offenders.append((file_path.relative_to(REPO_ROOT), idx, ch))
                        break

        self.assertEqual([], offenders, f"Found non-ASCII letters in user-facing surfaces: {offenders}")


if __name__ == "__main__":
    unittest.main()

