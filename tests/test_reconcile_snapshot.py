"""The reconciliation instrument names *why* two views of a period disagree.

All fixtures here are synthetic. Nothing in this file may read the maintainer's
real ``~/.gittan`` — every test that touches the observed cache passes an
explicit temp ``home``, and no test runs a rescan (that would read real sources).

The two signatures under test are the ones the manual pass found:
``EVIDENCE DECAY`` (GH-543's family — totals move) and ``RE-ATTRIBUTION``
(GH-544 — the total holds while the split collapses).
"""

from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.reconcile_signatures import (
    EVIDENCE_DECAY,
    MIXED,
    RE_ATTRIBUTION,
    STABLE,
    UPWARD_DRIFT,
    apply_redaction,
    build_json,
    compare_hours,
    redaction_map,
    render_text,
)
from scripts.reconcile_snapshot import (
    load_snapshot,
    main,
    month_bounds,
    observed_hours,
    resolve_window,
    sandboxed_gittan_home,
    snapshot_hours,
    snapshot_settings,
    snapshot_window,
)


def _pair(baseline, comparison, *, tolerance_pct=5.0, noise_floor=0.25):
    return compare_hours(
        baseline,
        comparison,
        baseline_label="before",
        comparison_label="after",
        tolerance_pct=tolerance_pct,
        noise_floor_hours=noise_floor,
    )


def _snapshot_payload(projects, *, date_from="2026-06-01", date_to="2026-06-30"):
    return {
        "schema": "timelog_extract.truth_payload",
        "version": "2",
        "generator": {"package": "timelog-extract", "version": "0.3.0"},
        "range": {"from": f"{date_from}T00:00:00+00:00", "to": f"{date_to}T23:59:59+00:00"},
        "settings": {
            "gap_minutes": 20,
            "min_session_minutes": 10,
            "min_session_passive_minutes": 4,
        },
        "projects": dict(projects),
        "days": {},
    }


def _write_observed(home: Path, rows) -> Path:
    base = home / ".gittan" / "observed"
    base.mkdir(parents=True, exist_ok=True)
    by_month = {}
    for project, day, hours in rows:
        by_month.setdefault(day[:7], []).append(
            {"project": project, "date": day, "hours": hours, "captured_at": f"{day}T09:54:00+00:00"}
        )
    for month, entries in by_month.items():
        path = base / f"{month}.jsonl"
        path.write_text(
            "".join(json.dumps(e, sort_keys=True) + "\n" for e in entries), encoding="utf-8"
        )
    return base


class DecompositionTests(unittest.TestCase):
    def test_gross_splits_exactly_into_net_and_reallocation(self):
        pair = _pair({"Alpha": 10.0, "Beta": 4.0}, {"Alpha": 6.0, "Beta": 5.0})
        self.assertAlmostEqual(pair.gross, abs(pair.net) + 2 * pair.moved, places=6)

    def test_pure_reallocation_has_zero_net_and_nonzero_moved(self):
        pair = _pair({"Alpha": 6.0, "Beta": 0.0}, {"Alpha": 0.0, "Beta": 6.0})
        self.assertEqual(pair.net, 0.0)
        self.assertEqual(pair.moved, 6.0)
        self.assertEqual(pair.shift_share, 1.0)

    def test_pure_scale_change_has_zero_moved(self):
        pair = _pair({"Alpha": 10.0, "Beta": 5.0}, {"Alpha": 8.0, "Beta": 4.0})
        self.assertEqual(pair.moved, 0.0)
        self.assertEqual(pair.shift_share, 0.0)

    def test_union_of_projects_covers_both_sides(self):
        pair = _pair({"Alpha": 1.0}, {"Beta": 1.0})
        self.assertEqual([row.project for row in pair.rows], ["Alpha", "Beta"])

    def test_a_project_present_on_one_side_only_is_flagged(self):
        pair = _pair({"Alpha": 1.0}, {"Beta": 1.0})
        by_name = {row.project: row for row in pair.rows}
        self.assertEqual(by_name["Alpha"].only_in, "baseline")
        self.assertEqual(by_name["Beta"].only_in, "comparison")

    def test_net_pct_is_none_when_the_baseline_is_empty(self):
        self.assertIsNone(_pair({}, {"Alpha": 3.0}).net_pct)


class SignatureTests(unittest.TestCase):
    def test_identical_views_are_stable(self):
        self.assertEqual(_pair({"Alpha": 8.0}, {"Alpha": 8.0}).signature, STABLE)

    def test_sub_noise_change_is_stable(self):
        self.assertEqual(_pair({"Alpha": 8.0}, {"Alpha": 8.1}).signature, STABLE)

    def test_totals_dropping_together_is_evidence_decay(self):
        pair = _pair({"Alpha": 10.0, "Beta": 6.0}, {"Alpha": 6.0, "Beta": 3.6})
        self.assertEqual(pair.signature, EVIDENCE_DECAY)

    def test_totals_growing_without_reallocation_is_upward_drift(self):
        # GH-543's June shape: the month reads ~30% higher than it did at invoice time.
        pair = _pair({"Alpha": 50.0, "Beta": 32.8}, {"Alpha": 64.0, "Beta": 43.5})
        self.assertEqual(pair.signature, UPWARD_DRIFT)
        self.assertGreater(pair.net_pct, 25.0)

    def test_total_held_while_the_split_moves_is_re_attribution(self):
        # GH-544's shape: a project collapses, the day total is preserved.
        pair = _pair({"Alpha": 1.65, "Beta": 4.60}, {"Alpha": 0.024, "Beta": 6.226})
        self.assertEqual(pair.signature, RE_ATTRIBUTION)
        self.assertGreater(pair.moved, 1.0)

    def test_scale_and_reallocation_together_is_mixed(self):
        pair = _pair({"Alpha": 10.0, "Beta": 10.0}, {"Alpha": 0.0, "Beta": 14.0})
        self.assertEqual(pair.signature, MIXED)

    def test_tolerance_widens_what_counts_as_a_held_total(self):
        baseline = {"Alpha": 10.0, "Beta": 10.0}
        comparison = {"Alpha": 6.0, "Beta": 12.0}  # shift share 0.67, below dominance
        self.assertEqual(_pair(baseline, comparison, tolerance_pct=1.0).signature, MIXED)
        self.assertEqual(_pair(baseline, comparison, tolerance_pct=15.0).signature, RE_ATTRIBUTION)

    def test_a_dominant_reallocation_outranks_a_residual_total_change(self):
        # GH-544 exactly: the total slipped ~7%, but 85% of the movement is a shuffle.
        pair = _pair({"Alpha": 1.65, "Beta": 4.60}, {"Alpha": 0.024, "Beta": 5.81})
        self.assertGreater(pair.shift_share, 0.75)
        self.assertGreater(abs(pair.net), pair.tolerance_hours)
        self.assertEqual(pair.signature, RE_ATTRIBUTION)

    def test_movers_are_ranked_by_absolute_delta_and_skip_noise(self):
        pair = _pair(
            {"Alpha": 10.0, "Beta": 5.0, "Gamma": 1.0},
            {"Alpha": 4.0, "Beta": 6.0, "Gamma": 1.1},
        )
        self.assertEqual([row.project for row in pair.movers()], ["Alpha", "Beta"])


class SnapshotParsingTests(unittest.TestCase):
    def test_projects_and_window_are_read_from_the_payload(self):
        payload = _snapshot_payload({"Alpha": 12.5, "Beta": 3.0})
        self.assertEqual(snapshot_hours(payload), {"Alpha": 12.5, "Beta": 3.0})
        self.assertEqual(snapshot_window(payload), ("2026-06-01", "2026-06-30"))

    def test_session_settings_are_carried_so_a_rescan_can_match_them(self):
        self.assertEqual(
            snapshot_settings(_snapshot_payload({})),
            {"gap_minutes": 20, "min_session_minutes": 10, "min_session_passive_minutes": 4},
        )

    def test_a_payload_without_projects_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "not-a-payload.json"
            path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshot(path)

    def test_a_payload_without_a_range_cannot_supply_a_window(self):
        with self.assertRaises(ValueError):
            snapshot_window({"projects": {}})

    def test_month_bounds_handle_month_length(self):
        self.assertEqual(month_bounds("2026-02"), ("2026-02-01", "2026-02-28"))
        self.assertEqual(month_bounds("2026-06"), ("2026-06-01", "2026-06-30"))
        self.assertEqual(month_bounds("2024-02"), ("2024-02-01", "2024-02-29"))


class ObservedCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_only_rows_inside_the_window_are_summed(self):
        _write_observed(
            self.home,
            [
                ("Alpha", "2026-05-31", 3.0),
                ("Alpha", "2026-06-01", 1.0),
                ("Alpha", "2026-06-30", 2.0),
                ("Beta", "2026-06-15", 4.0),
                ("Alpha", "2026-07-01", 9.0),
            ],
        )
        self.assertEqual(
            observed_hours(self.home, "2026-06-01", "2026-06-30"),
            {"Alpha": 3.0, "Beta": 4.0},
        )

    def test_a_missing_cache_is_an_empty_view_not_an_error(self):
        self.assertEqual(observed_hours(self.home, "2026-06-01", "2026-06-30"), {})

    def test_reading_the_cache_leaves_the_bytes_untouched(self):
        base = _write_observed(self.home, [("Alpha", "2026-06-02", 1.5)])
        month = base / "2026-06.jsonl"
        before = month.read_bytes()
        observed_hours(self.home, "2026-06-01", "2026-06-30")
        self.assertEqual(month.read_bytes(), before)


class SandboxTests(unittest.TestCase):
    def test_gittan_home_is_redirected_and_then_restored(self):
        previous = os.environ.get("GITTAN_HOME")
        with sandboxed_gittan_home() as sandbox:
            self.assertEqual(os.environ["GITTAN_HOME"], str(sandbox))
            self.assertNotEqual(os.environ["GITTAN_HOME"], str(Path.home()))
        self.assertEqual(os.environ.get("GITTAN_HOME"), previous)

    def test_the_sandbox_directory_is_removed_afterwards(self):
        with sandboxed_gittan_home() as sandbox:
            path = sandbox
        self.assertFalse(path.exists())

    def test_an_existing_value_is_restored_not_dropped(self):
        os.environ["GITTAN_HOME"] = "/nonexistent/sentinel"
        self.addCleanup(os.environ.pop, "GITTAN_HOME", None)
        with sandboxed_gittan_home():
            pass
        self.assertEqual(os.environ["GITTAN_HOME"], "/nonexistent/sentinel")


class RedactionTests(unittest.TestCase):
    def test_aliases_are_ordered_by_the_largest_hours_in_any_view(self):
        mapping = redaction_map({"snapshot": {"Small": 1.0, "Big": 9.0}, "rescan": {"Small": 12.0}})
        self.assertEqual(mapping, {"Small": "project-01", "Big": "project-02"})

    def test_hours_survive_redaction_unchanged(self):
        mapping = redaction_map({"snapshot": {"Alpha": 4.0}})
        self.assertEqual(apply_redaction({"Alpha": 4.0}, mapping), {"project-01": 4.0})

    def test_the_same_project_gets_the_same_alias_in_every_view(self):
        views = {"snapshot": {"Alpha": 9.0, "Beta": 1.0}, "observed": {"Beta": 2.0}}
        mapping = redaction_map(views)
        redacted = {name: apply_redaction(hours, mapping) for name, hours in views.items()}
        self.assertEqual(redacted["snapshot"], {"project-01": 9.0, "project-02": 1.0})
        self.assertEqual(redacted["observed"], {"project-02": 2.0})


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.views = {
            "snapshot": {"Alpha": 1.65, "Beta": 4.60},
            "observed": {"Alpha": 1.65, "Beta": 4.60},
            "rescan": {"Alpha": 0.02, "Beta": 5.81},
        }
        order = ["snapshot", "observed", "rescan"]
        self.pairs = [
            compare_hours(
                self.views[a],
                self.views[b],
                baseline_label=a,
                comparison_label=b,
                tolerance_pct=5.0,
                noise_floor_hours=0.25,
            )
            for a, b in [("snapshot", "observed"), ("observed", "rescan"), ("snapshot", "rescan")]
        ]
        self.order = order

    def test_the_table_names_the_signature_for_each_pair(self):
        text = render_text(("2026-08-07", "2026-08-07"), self.views, self.pairs, [])
        self.assertIn("observed -> rescan", text)
        self.assertIn(RE_ATTRIBUTION, text)

    def test_the_table_explains_what_the_columns_mean(self):
        text = render_text(("2026-08-07", "2026-08-07"), self.views, self.pairs, [])
        self.assertIn("How to read this:", text)
        for column in ("snapshot", "observed", "rescan", "net", "moved", "gross", "SIGNATURE"):
            self.assertIn(f"  {column}", text)

    def test_json_output_carries_the_decomposition_and_the_verdict(self):
        payload = build_json(("2026-08-07", "2026-08-07"), self.views, self.pairs, ["a note"])
        self.assertEqual(payload["window"], {"from": "2026-08-07", "to": "2026-08-07"})
        pair = next(p for p in payload["pairs"] if p["comparison"] == "rescan")
        self.assertIn("moved", pair)
        self.assertIn("signature", pair)
        self.assertIn("signature_meaning", pair)


class WindowResolutionTests(unittest.TestCase):
    class _Args:
        def __init__(self, **kwargs):
            self.date_from = kwargs.get("date_from")
            self.date_to = kwargs.get("date_to")
            self.period = kwargs.get("period")

    def test_explicit_dates_win(self):
        args = self._Args(date_from="2026-06-10", date_to="2026-06-12", period="2026-01")
        self.assertEqual(resolve_window(args, None), ("2026-06-10", "2026-06-12"))

    def test_a_period_expands_to_month_bounds(self):
        self.assertEqual(resolve_window(self._Args(period="2026-06"), None), month_bounds("2026-06"))

    def test_the_snapshot_supplies_the_window_when_nothing_else_does(self):
        payload = _snapshot_payload({}, date_from="2026-05-01", date_to="2026-05-31")
        self.assertEqual(resolve_window(self._Args(), payload), ("2026-05-01", "2026-05-31"))

    def test_no_window_at_all_is_an_error(self):
        with self.assertRaises(ValueError):
            resolve_window(self._Args(), None)

    def test_half_a_range_is_refused_rather_than_silently_replaced(self):
        # Falling through to --period or the snapshot would reconcile a window the
        # operator did not ask for and report drift for it successfully, which is
        # the failure mode this instrument exists to rule out.
        for kwargs in (
            {"date_from": "2026-06-10", "period": "2026-01"},
            {"date_to": "2026-06-12", "period": "2026-01"},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    resolve_window(self._Args(**kwargs), None)

    def test_half_a_range_is_refused_even_with_a_snapshot_available(self):
        payload = _snapshot_payload({}, date_from="2026-05-01", date_to="2026-05-31")
        with self.assertRaises(ValueError):
            resolve_window(self._Args(date_from="2026-06-10"), payload)


class CliTests(unittest.TestCase):
    """End-to-end through ``main``, always with ``--no-rescan`` and a temp home."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def _snapshot_file(self, projects, **kwargs):
        path = self.tmp / "snapshot.json"
        path.write_text(json.dumps(_snapshot_payload(projects, **kwargs)), encoding="utf-8")
        return path

    def _run(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_snapshot_versus_observed_reports_the_ratchet(self):
        self._write_cache([("Alpha", "2026-06-10", 64.0), ("Beta", "2026-06-11", 43.5)])
        snapshot = self._snapshot_file({"Alpha": 50.0, "Beta": 32.8})
        code, out = self._run(["--snapshot", str(snapshot), "--home", str(self.home), "--no-rescan"])
        self.assertEqual(code, 0)
        self.assertIn(UPWARD_DRIFT, out)
        self.assertIn("keep-max", out)

    def test_re_attribution_is_named_when_the_total_holds(self):
        self._write_cache([("Alpha", "2026-06-10", 0.02), ("Beta", "2026-06-10", 6.23)])
        snapshot = self._snapshot_file({"Alpha": 1.65, "Beta": 4.60})
        _code, out = self._run(
            ["--snapshot", str(snapshot), "--home", str(self.home), "--no-rescan"]
        )
        self.assertIn(RE_ATTRIBUTION, out)

    def test_redact_hides_project_names_but_keeps_the_hours(self):
        self._write_cache([("Acme Industries", "2026-06-10", 12.0)])
        code, out = self._run(
            ["--period", "2026-06", "--home", str(self.home), "--no-rescan", "--redact"]
        )
        self.assertEqual(code, 0)
        self.assertNotIn("Acme Industries", out)
        self.assertIn("project-01", out)
        self.assertIn("12.00", out)

    def test_json_mode_emits_parseable_output(self):
        self._write_cache([("Alpha", "2026-06-10", 3.0)])
        _code, out = self._run(
            ["--period", "2026-06", "--home", str(self.home), "--no-rescan", "--json"]
        )
        payload = json.loads(out)
        self.assertEqual(payload["views"]["observed"], {"Alpha": 3.0})

    def test_fail_on_drift_exits_two_only_when_a_pair_is_unstable(self):
        self._write_cache([("Alpha", "2026-06-10", 3.0)])
        snapshot = self._snapshot_file({"Alpha": 3.0})
        argv = [
            "--snapshot",
            str(snapshot),
            "--home",
            str(self.home),
            "--no-rescan",
            "--fail-on-drift",
        ]
        self.assertEqual(self._run(argv)[0], 0)
        drifted = self._snapshot_file({"Alpha": 30.0})
        argv[1] = str(drifted)
        self.assertEqual(self._run(argv)[0], 2)

    def test_a_missing_snapshot_is_a_usage_error_not_a_traceback(self):
        code, _out = self._run(["--snapshot", str(self.tmp / "nope.json"), "--no-rescan"])
        self.assertEqual(code, 1)

    def test_no_window_at_all_is_a_usage_error(self):
        self.assertEqual(self._run(["--home", str(self.home), "--no-rescan"])[0], 1)

    def test_the_run_never_writes_into_the_home_it_reads(self):
        base = self._write_cache([("Alpha", "2026-06-10", 3.0)])
        before = {p.name: p.read_bytes() for p in sorted(base.glob("*.jsonl"))}
        listing_before = sorted(p.name for p in self.home.rglob("*"))
        self._run(["--period", "2026-06", "--home", str(self.home), "--no-rescan"])
        self.assertEqual({p.name: p.read_bytes() for p in sorted(base.glob("*.jsonl"))}, before)
        self.assertEqual(sorted(p.name for p in self.home.rglob("*")), listing_before)

    def _write_cache(self, rows):
        return _write_observed(self.home, rows)


if __name__ == "__main__":
    unittest.main()
