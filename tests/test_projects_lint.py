"""Tests for core/projects_lint.py - lint_projects_payload() and LintWarning."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.projects_lint import (
    HIGH_RISK_TERMS,
    LintWarning,
    lint_projects_config,
    lint_projects_payload,
)


def _make_project(name, match_terms=None, customer=None, enabled=True, tracked_urls=None):
    p = {
        "name": name,
        "match_terms": match_terms or [],
        "enabled": enabled,
    }
    if customer is not None:
        p["customer"] = customer
    if tracked_urls is not None:
        p["tracked_urls"] = tracked_urls
    return p


class LintProjectsPayloadCleanConfigTests(unittest.TestCase):
    """A well-formed config with no overlaps should produce no warnings."""

    def test_empty_payload_no_warnings(self):
        self.assertEqual(lint_projects_payload({}), [])

    def test_empty_projects_list_no_warnings(self):
        self.assertEqual(lint_projects_payload({"projects": []}), [])

    def test_single_project_no_warnings(self):
        payload = {"projects": [_make_project("ProjectA", ["unique-term"])]}
        self.assertEqual(lint_projects_payload(payload), [])

    def test_non_overlapping_projects_no_warnings(self):
        payload = {
            "projects": [
                _make_project("Alpha", ["alpha-term"], customer="CustomerA"),
                _make_project("Beta", ["beta-term"], customer="CustomerB"),
            ]
        }
        self.assertEqual(lint_projects_payload(payload), [])


class LintProjectsPayloadBroadTermTests(unittest.TestCase):
    """Projects using HIGH_RISK_TERMS should produce broad-term warnings."""

    def test_high_risk_term_produces_warning(self):
        risky_term = next(iter(HIGH_RISK_TERMS))
        payload = {"projects": [_make_project("RiskyProject", [risky_term])]}
        warnings = lint_projects_payload(payload)
        codes = [w.code for w in warnings]
        self.assertIn("broad-term", codes)

    def test_broad_term_warning_message_contains_term_and_project(self):
        payload = {"projects": [_make_project("MyProject", ["koden"])]}
        warnings = lint_projects_payload(payload)
        broad_warnings = [w for w in warnings if w.code == "broad-term"]
        self.assertEqual(len(broad_warnings), 1)
        self.assertIn("koden", broad_warnings[0].message)
        self.assertIn("MyProject", broad_warnings[0].message)

    def test_all_high_risk_terms_each_produce_warning(self):
        for risky in HIGH_RISK_TERMS:
            with self.subTest(term=risky):
                payload = {"projects": [_make_project("P", [risky])]}
                warnings = lint_projects_payload(payload)
                broad = [w for w in warnings if w.code == "broad-term"]
                self.assertGreater(len(broad), 0)

    def test_non_high_risk_term_no_broad_warning(self):
        payload = {"projects": [_make_project("SafeProject", ["myapp-specific-term"])]}
        warnings = lint_projects_payload(payload)
        broad = [w for w in warnings if w.code == "broad-term"]
        self.assertEqual(broad, [])


class LintProjectsPayloadOverlapTermTests(unittest.TestCase):
    """Overlapping match_terms across different customers should produce overlap-term warnings."""

    def test_cross_customer_overlap_produces_warning(self):
        payload = {
            "projects": [
                _make_project("Alpha", ["shared-term"], customer="CustomerA"),
                _make_project("Beta", ["shared-term"], customer="CustomerB"),
            ]
        }
        warnings = lint_projects_payload(payload)
        codes = [w.code for w in warnings]
        self.assertIn("overlap-term", codes)

    def test_overlap_warning_message_contains_term_and_both_projects(self):
        payload = {
            "projects": [
                _make_project("Alpha", ["shared-keyword"], customer="CustomerA"),
                _make_project("Beta", ["shared-keyword"], customer="CustomerB"),
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertEqual(len(overlap), 1)
        self.assertIn("shared-keyword", overlap[0].message)
        self.assertIn("Alpha", overlap[0].message)
        self.assertIn("Beta", overlap[0].message)

    def test_same_customer_overlap_allowed(self):
        """Overlap within the same customer namespace should NOT produce a warning."""
        payload = {
            "projects": [
                _make_project("Alpha-Main", ["shared-term"], customer="SameCustomer"),
                _make_project("Alpha-Sub", ["shared-term"], customer="SameCustomer"),
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertEqual(overlap, [])

    def test_no_customer_overlap_produces_warning(self):
        """Overlap with no customer set is cross-namespace risk, should warn."""
        payload = {
            "projects": [
                _make_project("Alpha", ["shared-term"]),  # no customer
                _make_project("Beta", ["shared-term"]),   # no customer
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertGreater(len(overlap), 0)

    def test_no_overlap_for_unique_terms(self):
        payload = {
            "projects": [
                _make_project("Alpha", ["unique-a"], customer="CustomerA"),
                _make_project("Beta", ["unique-b"], customer="CustomerB"),
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertEqual(overlap, [])


class LintProjectsPayloadDisabledProjectTests(unittest.TestCase):
    """Disabled projects should be excluded from lint checks."""

    def test_disabled_project_excluded_from_overlap_check(self):
        payload = {
            "projects": [
                _make_project("Active", ["shared-term"], customer="CustomerA"),
                _make_project("Disabled", ["shared-term"], customer="CustomerB", enabled=False),
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertEqual(overlap, [])

    def test_disabled_project_excluded_from_broad_term_check(self):
        payload = {
            "projects": [
                _make_project("Disabled", ["koden"], enabled=False),
            ]
        }
        warnings = lint_projects_payload(payload)
        broad = [w for w in warnings if w.code == "broad-term"]
        self.assertEqual(broad, [])

    def test_non_dict_project_entries_skipped(self):
        """Non-dict entries in projects list should not cause errors."""
        payload = {"projects": [None, "string-value", 42, _make_project("Valid", ["myterm"])]}
        # Should not raise
        warnings = lint_projects_payload(payload)
        self.assertIsInstance(warnings, list)


class LintProjectsPayloadEmptyTermsTests(unittest.TestCase):
    """Empty or blank terms should be ignored."""

    def test_empty_match_term_ignored(self):
        payload = {
            "projects": [
                _make_project("Alpha", ["", "  ", "real-term"]),
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertEqual(warnings, [])

    def test_none_match_terms_ignored(self):
        payload = {"projects": [{"name": "P", "match_terms": None}]}
        warnings = lint_projects_payload(payload)
        self.assertIsInstance(warnings, list)


class LintWarningDataclassTests(unittest.TestCase):
    """LintWarning dataclass behaves as expected."""

    def test_lint_warning_has_code_and_message(self):
        w = LintWarning(code="overlap-term", message="some overlap")
        self.assertEqual(w.code, "overlap-term")
        self.assertEqual(w.message, "some overlap")

    def test_lint_warning_equality(self):
        w1 = LintWarning(code="broad-term", message="msg")
        w2 = LintWarning(code="broad-term", message="msg")
        self.assertEqual(w1, w2)


class LintProjectsConfigTests(unittest.TestCase):
    """Tests for lint_projects_config() file loading."""

    def test_lint_config_file_clean(self):
        payload = {
            "projects": [
                _make_project("SafeProject", ["unique-identifier"], customer="CustomerX"),
            ]
        }
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "timelog_projects.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")
            warnings = lint_projects_config(config_path)
            self.assertEqual(warnings, [])

    def test_lint_config_file_with_overlapping_terms(self):
        payload = {
            "projects": [
                _make_project("Alpha", ["shared-word"], customer="CustomerA"),
                _make_project("Beta", ["shared-word"], customer="CustomerB"),
            ]
        }
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "timelog_projects.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")
            warnings = lint_projects_config(config_path)
            overlap = [w for w in warnings if w.code == "overlap-term"]
            self.assertGreater(len(overlap), 0)


if __name__ == "__main__":
    unittest.main()