"""Unit tests for _resolve_only_project_filter in core/report_runtime.py."""

import argparse
import unittest

from core.report_runtime import _resolve_only_project_filter


def _ns(**kwargs):
    """Build an argparse.Namespace from keyword arguments."""
    return argparse.Namespace(**kwargs)


def _profiles(*names, aliases_map=None):
    """Build a minimal list of profile dicts from project names."""
    result = []
    for name in names:
        p = {"name": name}
        if aliases_map and name in aliases_map:
            p["aliases"] = aliases_map[name]
        result.append(p)
    return result


class ResolveOnlyProjectFilterExactMatchTests(unittest.TestCase):
    """Tests for exact name matching in _resolve_only_project_filter."""

    def test_exact_match_preserves_canonical_case(self):
        """Exact (case-insensitive) name match sets only_project to canonical name."""
        args = _ns(only_project="projA")
        profiles = _profiles("ProjA", "ProjB")
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "ProjA")

    def test_exact_match_uppercase_query(self):
        """Uppercase query still resolves to the canonical profile name."""
        args = _ns(only_project="PROJB")
        profiles = _profiles("ProjA", "ProjB")
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "ProjB")

    def test_exact_match_does_not_set_resolved_flag(self):
        """Exact match does NOT set only_project_resolved (only partial match does)."""
        args = _ns(only_project="ProjA")
        profiles = _profiles("ProjA")
        _resolve_only_project_filter(args, profiles)
        self.assertFalse(getattr(args, "only_project_resolved", False))

    def test_empty_only_project_returns_immediately(self):
        """Empty only_project causes early return with no attributes set."""
        args = _ns(only_project="")
        profiles = _profiles("ProjA")
        _resolve_only_project_filter(args, profiles)
        # No extra flags set
        self.assertFalse(getattr(args, "only_project_no_match", False))
        self.assertFalse(getattr(args, "only_project_resolved", False))

    def test_none_only_project_returns_immediately(self):
        """None only_project causes early return with no attributes set."""
        args = _ns(only_project=None)
        profiles = _profiles("ProjA")
        _resolve_only_project_filter(args, profiles)
        self.assertFalse(getattr(args, "only_project_no_match", False))


class ResolveOnlyProjectFilterPartialMatchTests(unittest.TestCase):
    """Tests for partial/substring name matching."""

    def test_unique_partial_match_resolves(self):
        """A partial match against exactly one profile resolves to that profile."""
        args = _ns(only_project="proj")
        profiles = _profiles("UniqueProjectX", "SomethingElse")
        # "proj" is in "uniqueprojectx" (lowercased): should match uniqueprojectx only
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "UniqueProjectX")
        self.assertTrue(getattr(args, "only_project_resolved", False))

    def test_partial_match_stores_original_input(self):
        """When partial match resolves, original input is stored in only_project_input."""
        args = _ns(only_project="unique")
        profiles = _profiles("UniqueProject")
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project_input, "unique")

    def test_alias_partial_match_resolves(self):
        """Partial match against an alias resolves to the canonical profile name."""
        args = _ns(only_project="shortname")
        profiles = _profiles("FullProjectName", aliases_map={"FullProjectName": ["shortname"]})
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project, "FullProjectName")


class ResolveOnlyProjectFilterAmbiguousTests(unittest.TestCase):
    """Tests for ambiguous partial matches (multiple candidates)."""

    def test_ambiguous_match_sets_ambiguous_flag(self):
        """When partial match is ambiguous, only_project_ambiguous is set."""
        args = _ns(only_project="proj")
        profiles = _profiles("ProjAlpha", "ProjBeta")
        _resolve_only_project_filter(args, profiles)
        ambiguous = getattr(args, "only_project_ambiguous", None)
        self.assertIsNotNone(ambiguous)
        self.assertIn("ProjAlpha", ambiguous)
        self.assertIn("ProjBeta", ambiguous)

    def test_ambiguous_candidates_sorted_alphabetically(self):
        """Ambiguous candidates list is sorted case-insensitively."""
        args = _ns(only_project="proj")
        profiles = _profiles("ProjZeta", "ProjAlpha", "ProjMid")
        _resolve_only_project_filter(args, profiles)
        ambiguous = getattr(args, "only_project_ambiguous", [])
        self.assertEqual(ambiguous, sorted(ambiguous, key=str.lower))

    def test_ambiguous_match_does_not_change_only_project(self):
        """When ambiguous, only_project retains the user's original input."""
        args = _ns(only_project="proj")
        profiles = _profiles("ProjA", "ProjB")
        _resolve_only_project_filter(args, profiles)
        # only_project should still be the original value (not changed to a canonical name)
        self.assertEqual(args.only_project, "proj")


class ResolveOnlyProjectFilterNoMatchTests(unittest.TestCase):
    """Tests for when no profile matches the filter."""

    def test_no_match_sets_no_match_flag(self):
        """When no profile matches, only_project_no_match is set to True."""
        args = _ns(only_project="zzznomatch")
        profiles = _profiles("Alpha", "Beta")
        _resolve_only_project_filter(args, profiles)
        self.assertTrue(getattr(args, "only_project_no_match", False))

    def test_no_match_stores_original_input(self):
        """When no match found, original input is stored in only_project_input."""
        args = _ns(only_project="zzznomatch")
        profiles = _profiles("Alpha")
        _resolve_only_project_filter(args, profiles)
        self.assertEqual(args.only_project_input, "zzznomatch")

    def test_empty_profiles_no_match(self):
        """Empty profiles list results in no-match flag."""
        args = _ns(only_project="anything")
        _resolve_only_project_filter(args, [])
        self.assertTrue(getattr(args, "only_project_no_match", False))


class ResolveOnlyProjectFilterEdgeCasesTests(unittest.TestCase):
    """Edge cases and regression scenarios."""

    def test_profile_with_empty_name_skipped(self):
        """Profiles with empty name are not considered in matching."""
        args = _ns(only_project="something")
        profiles = [{"name": ""}, {"name": "RealProject"}]
        _resolve_only_project_filter(args, profiles)
        # "something" is not in "realproject" so should be no match
        self.assertTrue(getattr(args, "only_project_no_match", False))

    def test_duplicate_profile_names_not_duplicated_in_ambiguous(self):
        """The same canonical name is not listed twice in ambiguous list."""
        args = _ns(only_project="proj")
        profiles = _profiles("ProjAlpha", "ProjAlpha")  # duplicate
        _resolve_only_project_filter(args, profiles)
        ambiguous = getattr(args, "only_project_ambiguous", None)
        # With two identical profiles, only one unique candidate
        if ambiguous is not None:
            self.assertEqual(len(ambiguous), 1)
        else:
            # Could resolve to single match
            self.assertEqual(args.only_project, "ProjAlpha")

    def test_whitespace_only_project_treated_as_empty(self):
        """Whitespace-only only_project is treated as empty (early return)."""
        args = _ns(only_project="   ")
        profiles = _profiles("ProjA")
        _resolve_only_project_filter(args, profiles)
        self.assertFalse(getattr(args, "only_project_no_match", False))
        self.assertFalse(getattr(args, "only_project_resolved", False))


if __name__ == "__main__":
    unittest.main()