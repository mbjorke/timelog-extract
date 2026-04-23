"""Tests for _resolve_only_project_filter() in core/report_runtime.py."""

import argparse
import unittest

from core.report_runtime import _resolve_only_project_filter


def _args(**kwargs):
    ns = argparse.Namespace()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def _profile(name, aliases=None, customer=None):
    p = {"name": name}
    if aliases:
        p["aliases"] = aliases
    if customer:
        p["customer"] = customer
    return p


class ResolveOnlyProjectFilterExactMatchTests(unittest.TestCase):
    """Exact name matches (case-insensitive) resolve without ambiguity."""

    def test_exact_match_preserves_canonical_name(self):
        args = _args(only_project="alpha")
        profiles = [_profile("Alpha"), _profile("Beta")]
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "Alpha")

    def test_exact_match_case_insensitive(self):
        args = _args(only_project="ALPHA")
        profiles = [_profile("Alpha"), _profile("Beta")]
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "Alpha")

    def test_exact_match_does_not_set_resolved_flag(self):
        # Exact match uses the fast path; resolved flag is only for partial match
        args = _args(only_project="Alpha")
        profiles = [_profile("Alpha")]
        _resolve_only_project_filter(args, profiles)
        self.assertFalse(getattr(args, "only_project_resolved", False))

    def test_exact_match_does_not_set_ambiguous_flag(self):
        args = _args(only_project="Alpha")
        profiles = [_profile("Alpha"), _profile("Beta")]
        _resolve_only_project_filter(args, profiles)
        ambiguous = getattr(args, "only_project_ambiguous", None)
        self.assertFalse(bool(ambiguous))


class ResolveOnlyProjectFilterPartialMatchTests(unittest.TestCase):
    """Partial (substring) matches on name or aliases."""

    def test_partial_match_single_candidate_resolves(self):
        args = _args(only_project="alph")
        profiles = [_profile("Alpha"), _profile("Gamma")]
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "Alpha")
        self.assertTrue(getattr(args, "only_project_resolved", False))

    def test_partial_match_sets_input_attribute(self):
        args = _args(only_project="alph")
        profiles = [_profile("Alpha")]
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project_input, "alph")

    def test_partial_match_via_alias(self):
        args = _args(only_project="proj-alias")
        profiles = [_profile("ProjectA", aliases=["proj-alias"])]
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "ProjectA")

    def test_multiple_partial_matches_sets_ambiguous(self):
        args = _args(only_project="proj")
        profiles = [_profile("ProjectAlpha"), _profile("ProjectBeta"), _profile("Gamma")]
        _resolve_only_project_filter(args, profiles)
        ambiguous = getattr(args, "only_project_ambiguous", None)
        self.assertIsNotNone(ambiguous)
        self.assertIn("ProjectAlpha", ambiguous)
        self.assertIn("ProjectBeta", ambiguous)
        self.assertNotIn("Gamma", ambiguous)

    def test_ambiguous_list_is_sorted(self):
        args = _args(only_project="proj")
        profiles = [_profile("Zebra-proj"), _profile("Alpha-proj")]
        _resolve_only_project_filter(args, profiles)
        ambiguous = getattr(args, "only_project_ambiguous", [])
        self.assertEqual(ambiguous, sorted(ambiguous, key=str.lower))

    def test_ambiguous_does_not_modify_only_project(self):
        """When ambiguous, the original only_project value should be preserved."""
        args = _args(only_project="proj")
        profiles = [_profile("ProjectAlpha"), _profile("ProjectBeta")]
        _resolve_only_project_filter(args, profiles)
        # only_project should remain the original search term since no resolution happened
        self.assertEqual(args.only_project, "proj")


class ResolveOnlyProjectFilterNoMatchTests(unittest.TestCase):
    """No match behavior."""

    def test_no_match_sets_no_match_flag(self):
        args = _args(only_project="zzz-nonexistent")
        profiles = [_profile("Alpha"), _profile("Beta")]
        _resolve_only_project_filter(args, profiles)
        self.assertTrue(getattr(args, "only_project_no_match", False))

    def test_no_match_preserves_input(self):
        args = _args(only_project="nonexistent")
        profiles = [_profile("Alpha")]
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project_input, "nonexistent")


class ResolveOnlyProjectFilterEmptyTests(unittest.TestCase):
    """Empty or absent only_project is a no-op."""

    def test_empty_string_is_noop(self):
        args = _args(only_project="")
        profiles = [_profile("Alpha")]
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "")
        self.assertFalse(getattr(args, "only_project_resolved", False))
        self.assertFalse(getattr(args, "only_project_no_match", False))

    def test_missing_attribute_is_noop(self):
        args = argparse.Namespace()
        profiles = [_profile("Alpha")]
        _resolve_only_project_filter(args, profiles)
        self.assertFalse(getattr(args, "only_project_resolved", False))

    def test_none_is_noop(self):
        args = _args(only_project=None)
        profiles = [_profile("Alpha")]
        _resolve_only_project_filter(args, profiles)
        self.assertFalse(getattr(args, "only_project_no_match", False))

    def test_empty_profiles_with_filter_sets_no_match(self):
        args = _args(only_project="something")
        _resolve_only_project_filter(args, [])
        self.assertTrue(getattr(args, "only_project_no_match", False))

    def test_no_duplicate_candidates_from_same_profile(self):
        """Same profile should only appear once in candidates."""
        args = _args(only_project="alpha")
        # Profile with name and alias both matching
        profiles = [_profile("ProjectAlpha", aliases=["alpha-alias"])]
        _resolve_only_project_filter(args, profiles)
        # Should resolve to single candidate
        self.assertEqual(args.only_project, "ProjectAlpha")
        self.assertFalse(bool(getattr(args, "only_project_ambiguous", None)))


if __name__ == "__main__":
    unittest.main()