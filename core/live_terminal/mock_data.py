"""Deterministic demo fixture loader shared by demo + tests."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_fixture_path() -> Path:
    override = str(os.environ.get("GITTAN_DEMO_MOCK_DATA", "") or "").strip()
    return Path(override).expanduser() if override else (_repo_root() / "tests" / "fixtures" / "demo_mock_data.json")


@lru_cache(maxsize=8)
def _load_demo_mock_data_from_path(path_key: str) -> Dict[str, Any]:
    fixture_path = Path(path_key)
    if not fixture_path.is_file():
        raise FileNotFoundError(f"Demo mock fixture not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def load_demo_mock_data() -> Dict[str, Any]:
    fixture_path = _resolve_fixture_path()
    return _load_demo_mock_data_from_path(str(fixture_path))

