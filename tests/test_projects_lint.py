"""Unit tests for core/projects_lint.py lint helpers."""

import unittest

from core.projects_lint import HIGH_RISK_TERMS, LintWarning, lint_projects_payload


def _project(name, match_terms=None, enabled=True, customer=None):
    """Helper to build a minimal project dict."""
    p = {
        "name": name,
        "match_terms": match_terms or [],
        "enabled": enabled,
    }
    if customer is not None:
        p["customer"] = customer
    return p


class LintWarningDataclassTests(unittest.TestCase):
    """Tests for the LintWarning dataclass."""

    def test_creates_with_code_and_message(self):
        """LintWarning stores code and message."""
        w = LintWarning(code="broad-term", message="some message")
        self.assertEqual(w.code, "broad-term")
        self.assertEqual(w.message, "some message")

    def test_repr_is_deterministic(self):
        """Two identical LintWarning instances have the same repr."""
        w1 = LintWarning(code="x", message="y")
        w2 = LintWarning(code="x", message="y")
        self.assertEqual(repr(w1), repr(w2))


class LintProjectsPayloadNoWarningsTests(unittest.TestCase):
    """Cases where lint_projects_payload should return no warnings."""

    def test_empty_payload_returns_no_warnings(self):
        """Empty projects list returns no warnings."""
        result = lint_projects_payload({"projects": []})
        self.assertEqual(result, [])

    def test_single_clean_project_returns_no_warnings(self):
        """Single project with non-overlapping, non-risky terms returns no warnings."""
        payload = {"projects": [_project("ProjectA", match_terms=["uniqueterm"])]}
        result = lint_projects_payload(payload)
        self.assertEqual(result, [])

    def test_disabled_project_skipped(self):
        """Disabled projects are not included in lint checks."""
        payload = {
            "projects": [
                _project("ProjectA", match_terms=["shared"], enabled=True),
                _project("ProjectB", match_terms=["shared"], enabled=False),
            ]
        }
        result = lint_projects_payload(payload)
        # Only one enabled project uses "shared" -> no overlap warning
        self.assertEqual(result, [])

    def test_same_term_same_customer_no_overlap_warning(self):
        """Overlapping terms inside the same customer namespace do not produce a warning."""
        payload = {
            "projects": [
                _project("ProjA", match_terms=["sharedterm"], customer="Acme"),
                _project("ProjB", match_terms=["sharedterm"], customer="acme"),  # same customer, lowercase
            ]
        }
        result = lint_projects_payload(payload)
        overlap_warnings = [w for w in result if w.code == "overlap-term"]
        self.assertEqual(overlap_warnings, [])

    def test_non_dict_project_entry_skipped(self):
        """Non-dict entries in projects list are silently skipped."""
        payload = {"projects": ["not-a-dict", None, 42]}
        result = lint_projects_payload(payload)
        self.assertEqual(result, [])

    def test_blank_match_term_skipped(self):
        """Empty or whitespace match terms are ignored."""
        payload = {"projects": [_project("P", match_terms=["", "  ", None])]}
        result = lint_projects_payload(payload)
        self.assertEqual(result, [])


class LintProjectsPayloadOverlapTests(unittest.TestCase):
    """Cases where overlap-term warnings should be raised."""

    def test_same_term_different_customers_triggers_overlap(self):
        """Same term in two projects from different customers triggers overlap-term."""
        payload = {
            "projects": [
                _project("ProjA", match_terms=["sharedterm"], customer="CustomerA"),
                _project("ProjB", match_terms=["sharedterm"], customer="CustomerB"),
            ]
        }
        result = lint_projects_payload(payload)
        codes = [w.code for w in result]
        self.assertIn("overlap-term", codes)

    def test_same_term_no_customer_triggers_overlap(self):
        """Same term in two projects with no customer set triggers overlap-term."""
        payload = {
            "projects": [
                _project("Alpha", match_terms=["commonterm"]),
                _project("Beta", match_terms=["commonterm"]),
            ]
        }
        result = lint_projects_payload(payload)
        codes = [w.code for w in result]
        self.assertIn("overlap-term", codes)

    def test_overlap_warning_message_includes_term_and_projects(self):
        """Overlap warning message names the overlapping term and both projects."""
        payload = {
            "projects": [
                _project("Alpha", match_terms=["myterm"]),
                _project("Beta", match_terms=["myterm"]),
            ]
        }
        result = lint_projects_payload(payload)
        overlap = [w for w in result if w.code == "overlap-term"]
        self.assertEqual(len(overlap), 1)
        self.assertIn("myterm", overlap[0].message)
        self.assertIn("Alpha", overlap[0].message)
        self.assertIn("Beta", overlap[0].message)

    def test_three_projects_sharing_term_triggers_one_overlap_warning(self):
        """Three projects sharing the same term produce one overlap-term warning."""
        payload = {
            "projects": [
                _project("P1", match_terms=["shared"]),
                _project("P2", match_terms=["shared"]),
                _project("P3", match_terms=["shared"]),
            ]
        }
        result = lint_projects_payload(payload)
        overlap = [w for w in result if w.code == "overlap-term"]
        self.assertEqual(len(overlap), 1)

    def test_multiple_overlapping_terms_produce_one_warning_each(self):
        """Each unique overlapping term generates exactly one overlap warning."""
        payload = {
            "projects": [
                _project("P1", match_terms=["term1", "term2"]),
                _project("P2", match_terms=["term1", "term2"]),
            ]
        }
        result = lint_projects_payload(payload)
        overlap = [w for w in result if w.code == "overlap-term"]
        self.assertEqual(len(overlap), 2)


class LintProjectsPayloadBroadTermTests(unittest.TestCase):
    """Cases where broad-term warnings should be raised."""

    def test_high_risk_term_triggers_broad_term_warning(self):
        """A known high-risk broad term generates a broad-term warning."""
        risky_term = next(iter(HIGH_RISK_TERMS))
        payload = {"projects": [_project("P", match_terms=[risky_term])]}
        result = lint_projects_payload(payload)
        codes = [w.code for w in result]
        self.assertIn("broad-term", codes)

    def test_broad_term_warning_message_includes_term_and_project(self):
        """broad-term warning message names the term and the project."""
        risky_term = "koden"
        payload = {"projects": [_project("MyProject", match_terms=[risky_term])]}
        result = lint_projects_payload(payload)
        broad = [w for w in result if w.code == "broad-term"]
        self.assertEqual(len(broad), 1)
        self.assertIn("koden", broad[0].message)
        self.assertIn("MyProject", broad[0].message)

    def test_high_risk_terms_set_contains_expected_entries(self):
        """HIGH_RISK_TERMS set contains known risky Swedish terms."""
        self.assertIn("koden", HIGH_RISK_TERMS)
        self.assertIn("formulär", HIGH_RISK_TERMS)
        self.assertIn("lösenord", HIGH_RISK_TERMS)

    def test_non_high_risk_term_does_not_trigger_broad_warning(self):
        """A regular project-specific term does not trigger broad-term."""
        payload = {"projects": [_project("P", match_terms=["uniqueprojectidentifier"])]}
        result = lint_projects_payload(payload)
        codes = [w.code for w in result]
        self.assertNotIn("broad-term", codes)

    def test_disabled_project_with_high_risk_term_skipped(self):
        """A disabled project's high-risk terms are not flagged."""
        risky_term = "koden"
        payload = {"projects": [_project("P", match_terms=[risky_term], enabled=False)]}
        result = lint_projects_payload(payload)
        self.assertEqual(result, [])

    def test_all_high_risk_terms_trigger_warnings(self):
        """Every term in HIGH_RISK_TERMS triggers a broad-term warning."""
        for term in HIGH_RISK_TERMS:
            with self.subTest(term=term):
                payload = {"projects": [_project("P", match_terms=[term])]}
                result = lint_projects_payload(payload)
                codes = [w.code for w in result]
                self.assertIn("broad-term", codes)

    def test_match_terms_case_insensitive_lookup(self):
        """High-risk term check is case-insensitive (terms are lowercased)."""
        payload = {"projects": [_project("P", match_terms=["KODEN"])]}
        result = lint_projects_payload(payload)
        # "KODEN".strip().lower() == "koden" which IS in HIGH_RISK_TERMS
        codes = [w.code for w in result]
        self.assertIn("broad-term", codes)


class LintProjectsPayloadMixedTests(unittest.TestCase):
    """Cases that mix multiple warning types."""

    def test_both_overlap_and_broad_term_can_occur_together(self):
        """A risky term that is also shared across projects generates both warning types."""
        risky_term = "koden"
        payload = {
            "projects": [
                _project("P1", match_terms=[risky_term]),
                _project("P2", match_terms=[risky_term]),
            ]
        }
        result = lint_projects_payload(payload)
        codes = {w.code for w in result}
        self.assertIn("broad-term", codes)
        self.assertIn("overlap-term", codes)

    def test_payload_without_projects_key_returns_no_warnings(self):
        """Payload without 'projects' key is handled gracefully."""
        result = lint_projects_payload({})
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()