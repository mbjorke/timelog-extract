"""Deterministic demo fixture loader shared by demo + tests."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_demo_mock_data() -> Dict[str, Any]:
    fixture_path = _repo_root() / "tests" / "fixtures" / "demo_mock_data.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))

