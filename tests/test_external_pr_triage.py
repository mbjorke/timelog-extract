"""Tests for scripts/external_pr_triage_classify.py.

The classifier decides auto-close vs needs-review for an external PR from
metadata only. Auto-close must be narrow (the link-rot spam signature) so a
genuine first-time contributor is never slammed.
"""

from __future__ import annotations

import unittest

from scripts.external_pr_triage_classify import (
    classify_external_pr,
    has_archive_downgrade,
    is_docs_only,
    is_external_author,
)

# The real probe signature (PR #433): a live pipx link swapped for an http
# web.archive.org snapshot, in a docs-only "fix broken link" PR.
_ARCHIVE_PATCH = (
    "@@ -12,1 +12,1 @@\n"
    "-...uses [pipx](https://pypa.github.io/pipx/) under the hood...\n"
    "+...uses [pipx](http://web.archive.org/web/20231205060507/"
    "https://pypa.github.io/pipx/) under the hood...\n"
)


def _classify(**over):
    base = dict(
        author_association="NONE",
        changed_files=["README.md"],
        title="docs: fix 1 broken link(s) via Wayback",
        body="",
        patches=[_ARCHIVE_PATCH],
    )
    base.update(over)
    return classify_external_pr(**base)


class ExternalPrClassifyTests(unittest.TestCase):
    def test_link_rot_spam_signature_auto_closes(self):
        action, reason = _classify()
        self.assertEqual(action, "auto-close")
        self.assertIn("web.archive.org", reason)

    def test_real_first_time_contributor_docs_pr_is_reviewed_not_closed(self):
        # A genuine docs PR (no archive.org swap) must never auto-close.
        action, _ = _classify(
            title="docs: clarify install steps",
            patches=["@@ -1 +1 @@\n-old text\n+clearer text\n"],
        )
        self.assertEqual(action, "needs-review")

    def test_archive_link_without_link_fix_claim_is_reviewed(self):
        # Adds an archive.org link but the PR does not claim a link fix → not the
        # signature; err toward review.
        action, _ = _classify(title="docs: add a reference", body="see the archive")
        self.assertEqual(action, "needs-review")

    def test_code_change_never_auto_closes_even_with_signature(self):
        # Not docs-only (touches code) → review, never auto-close.
        action, _ = _classify(changed_files=["README.md", "core/domain.py"])
        self.assertEqual(action, "needs-review")

    def test_empty_changed_files_is_not_docs_only(self):
        self.assertFalse(is_docs_only([]))

    def test_docs_only_accepts_docs_dir_and_doc_suffixes(self):
        self.assertTrue(is_docs_only(["README.md", "docs/runbooks/x.md", "CONTRIBUTING.md"]))
        self.assertFalse(is_docs_only(["README.md", "pyproject.toml"]))
        self.assertFalse(is_docs_only([".github/workflows/ci.yml"]))

    def test_archive_downgrade_only_counts_added_lines(self):
        added = ["+ http://web.archive.org/web/x/https://a\n-https://a\n"]
        removed = ["-http://web.archive.org/web/x/https://a\n+https://a\n"]
        self.assertTrue(has_archive_downgrade(added))
        self.assertFalse(has_archive_downgrade(removed))

    def test_external_author_detection(self):
        for assoc in ("NONE", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "CONTRIBUTOR"):
            self.assertTrue(is_external_author(assoc), assoc)
        for assoc in ("OWNER", "MEMBER", "COLLABORATOR", "owner"):
            self.assertFalse(is_external_author(assoc), assoc)


if __name__ == "__main__":
    unittest.main()
