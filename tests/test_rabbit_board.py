"""Unit tests for scripts/rabbit_board.py (mocked gh — no live board writes)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
BOARD_PY = REPO_ROOT / "scripts" / "rabbit_board.py"


def _load_board():
    spec = importlib.util.spec_from_file_location("rabbit_board", BOARD_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RabbitBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BOARD_PY.is_file():
            raise unittest.SkipTest("rabbit_board.py missing")
        cls.board = _load_board()

    def test_status_field_option_resolves_by_name(self):
        fields_json = json.dumps(
            {
                "fields": [
                    {
                        "id": "field-1",
                        "name": "Status",
                        "options": [
                            {"id": "opt-a", "name": "In review"},
                            {"id": "opt-b", "name": "Done"},
                        ],
                    }
                ]
            }
        )

        def fake_run(args, **kwargs):
            if args[:3] == ["gh", "project", "field-list"]:
                return subprocess.CompletedProcess(args, 0, fields_json, "")
            raise AssertionError(f"unexpected gh call: {args}")

        with patch.object(self.board, "_run_gh", side_effect=fake_run):
            field_id, option_id = self.board.status_field_option("owner-a", 3, "In review")
        self.assertEqual(field_id, "field-1")
        self.assertEqual(option_id, "opt-a")

    def test_find_item_by_url_returns_none_when_missing(self):
        empty_page = {
            "data": {
                "user": {
                    "projectV2": {
                        "items": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [],
                        }
                    }
                }
            }
        }
        with patch.object(self.board, "_graphql", return_value=empty_page):
            missing = self.board.find_item_by_url("owner-a", 3, "https://github.com/o/r/issues/99")
        self.assertIsNone(missing)

    def test_find_item_by_url_finds_pr_on_second_page(self):
        page1 = {
            "data": {
                "user": {
                    "projectV2": {
                        "items": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                            "nodes": [
                                {"id": "item-1", "content": {"url": "https://github.com/o/r/issues/1"}},
                            ],
                        }
                    }
                }
            }
        }
        page2 = {
            "data": {
                "user": {
                    "projectV2": {
                        "items": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "item-2",
                                    "content": {"url": "https://github.com/o/r/pull/9"},
                                },
                            ],
                        }
                    }
                }
            }
        }

        with patch.object(self.board, "_graphql", side_effect=[page1, page2]):
            found = self.board.find_item_by_url("owner-a", 3, "https://github.com/o/r/pull/9")
        self.assertEqual(found, "item-2")

    def test_sync_content_url_dry_run_without_writes(self):
        fields_json = json.dumps(
            {
                "fields": [
                    {
                        "id": "field-1",
                        "name": "Status",
                        "options": [{"id": "opt-a", "name": "In review"}],
                    }
                ]
            }
        )
        graphql_page = {
            "data": {
                "user": {
                    "projectV2": {
                        "items": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [],
                        }
                    }
                }
            }
        }

        def fake_run(args, **kwargs):
            if args[:3] == ["gh", "project", "field-list"]:
                return subprocess.CompletedProcess(args, 0, fields_json, "")
            raise AssertionError(f"unexpected gh call in dry-run: {args}")

        with patch.object(self.board, "_run_gh", side_effect=fake_run):
            with patch.object(self.board, "_graphql", return_value=graphql_page):
                out = self.board.sync_content_url(
                    owner="owner-a",
                    project_number=3,
                    content_url="https://github.com/o/r/pull/42",
                    status_name="In review",
                    dry_run=True,
                )
        self.assertTrue(out.startswith("dry-run:add:"))

    def test_graphql_errors_fail_closed(self):
        with patch.object(
            self.board,
            "_run_gh",
            return_value=subprocess.CompletedProcess([], 0, json.dumps({"errors": [{"message": "nope"}]}), ""),
        ):
            with self.assertRaises(self.board.BoardError) as ctx:
                self.board._graphql("owner-a", 3, "query {}", after=None)
        self.assertIn("nope", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
