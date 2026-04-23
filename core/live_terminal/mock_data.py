"""Deterministic demo fixture loader shared by demo + tests."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_demo_mock_data() -> Dict[str, Any]:
    override = str(os.environ.get("GITTAN_DEMO_MOCK_DATA", "") or "").strip()
    fixture_path = Path(override).expanduser() if override else (_repo_root() / "tests" / "fixtures" / "demo_mock_data.json")
    if not fixture_path.is_file():
        raise FileNotFoundError(f"Demo mock fixture not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))

