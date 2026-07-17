"""Tests for the Toggl push operation log + rollback (#265)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from collectors.toggl import TogglCredentials
from core.toggl_oplog import (
    list_ops,
    new_op_id,
    oplog_path,
    payload_hash,
    read_oplog,
    record_push,
    rows_for_op,
)
from core.toggl_sync import rollback_op

_CREDS = TogglCredentials(api_token="fake", workspace_id=42)


def _record(home: Path, op_id: str, entry_id: str, day: str = "2026-06-23", project_id: int = 123):
    return record_push(
        op_id=op_id,
        workspace_id=42,
        entry_id=entry_id,
        project_id=project_id,
        day=day,
        marker_tag=f"gittan:{project_id}:{day}",
        payload={"project_id": project_id, "day": day},
        home=home,
    )


class OpLogWriteReadTests(unittest.TestCase):
    def test_op_id_is_unique_and_shaped(self):
        a, b = new_op_id(), new_op_id()
        self.assertNotEqual(a, b)
        self.assertRegex(a, r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")

    def test_payload_hash_is_stable_and_order_independent(self):
        self.assertEqual(payload_hash({"a": 1, "b": 2}), payload_hash({"b": 2, "a": 1}))

    def test_record_then_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            op = new_op_id()
            _record(home, op, "e1")
            _record(home, op, "e2", project_id=456)
            rows = read_oplog(home)
            self.assertEqual(len(rows), 2)
            self.assertEqual({r.entry_id for r in rows}, {"e1", "e2"})
            self.assertTrue(all(not r.rolled_back for r in rows))
            self.assertTrue(oplog_path(home).is_file())

    def test_corrupt_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            _record(home, new_op_id(), "e1")
            with oplog_path(home).open("a", encoding="utf-8") as fh:
                fh.write("{not json\n\n")
            self.assertEqual(len(read_oplog(home)), 1)

    def test_list_ops_groups_and_counts(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            op1, op2 = new_op_id(), new_op_id()
            _record(home, op1, "e1")
            _record(home, op2, "e2")
            _record(home, op2, "e3")
            ops = {o["op_id"]: o for o in list_ops(home)}
            self.assertEqual(ops[op2]["entries"], 2)
            self.assertEqual(ops[op1]["entries"], 1)


class RollbackTests(unittest.TestCase):
    def _delete_ok(self, creds, entry_id):
        self.deleted.append(entry_id)
        return "deleted"

    def setUp(self):
        self.deleted: list = []

    def test_rollback_deletes_all_entries_and_flags_them(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            op = new_op_id()
            _record(home, op, "e1")
            _record(home, op, "e2")
            res = rollback_op(_CREDS, op, delete_fn=self._delete_ok, home=home)
            self.assertEqual(res.deleted, 2)
            self.assertEqual(sorted(self.deleted), ["e1", "e2"])
            self.assertTrue(all(r.rolled_back for r in rows_for_op(op, home=home)))

    def test_rollback_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            op = new_op_id()
            _record(home, op, "e1")
            rollback_op(_CREDS, op, delete_fn=self._delete_ok, home=home)
            self.deleted.clear()
            res2 = rollback_op(_CREDS, op, delete_fn=self._delete_ok, home=home)
            self.assertEqual(res2.deleted, 0)
            self.assertEqual(res2.already, 1)
            self.assertEqual(self.deleted, [])  # no second network call

    def test_missing_entry_counts_as_gone_and_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            op = new_op_id()
            _record(home, op, "ghost")
            res = rollback_op(_CREDS, op, delete_fn=lambda c, e: "gone", home=home)
            self.assertEqual(res.gone, 1)
            self.assertTrue(rows_for_op(op, home=home)[0].rolled_back)

    def test_failed_delete_keeps_row_for_retry(self):
        def boom(creds, entry_id):
            raise RuntimeError("network down")

        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            op = new_op_id()
            _record(home, op, "e1")
            res = rollback_op(_CREDS, op, delete_fn=boom, home=home)
            self.assertEqual(res.failed, 1)
            # Not flagged rolled back, so a later retry will attempt it again.
            self.assertFalse(rows_for_op(op, home=home)[0].rolled_back)

    def test_unknown_op_id_is_a_clean_noop(self):
        with tempfile.TemporaryDirectory() as d:
            res = rollback_op(_CREDS, "nope", delete_fn=self._delete_ok, home=Path(d))
            self.assertEqual((res.deleted, res.gone, res.failed), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
