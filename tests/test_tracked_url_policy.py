"""Tests for multi-tenant tracked_urls policy helpers."""

from __future__ import annotations

import unittest

from core.tracked_url_policy import is_multi_tenant_tracked_url_host, is_over_broad_tracked_url


class TrackedUrlPolicyTests(unittest.TestCase):
    def test_multi_tenant_host_detection(self):
        self.assertTrue(is_multi_tenant_tracked_url_host("gemini.google.com"))
        self.assertTrue(is_multi_tenant_tracked_url_host("https://claude.ai/chat/abc"))
        self.assertFalse(is_multi_tenant_tracked_url_host("github.com/org/repo"))

    def test_over_broad_host_only_and_app_prefix(self):
        self.assertTrue(is_over_broad_tracked_url("gemini.google.com"))
        self.assertTrue(is_over_broad_tracked_url("claude.ai"))
        self.assertTrue(is_over_broad_tracked_url("gemini.google.com/app"))
        self.assertTrue(is_over_broad_tracked_url("claude.ai/chat"))

    def test_specific_chat_urls_are_allowed(self):
        self.assertFalse(is_over_broad_tracked_url("gemini.google.com/app/abc123"))
        self.assertFalse(is_over_broad_tracked_url("claude.ai/chat/specific-id"))
        self.assertFalse(is_over_broad_tracked_url("claude.ai/project_name"))
        self.assertFalse(is_over_broad_tracked_url("github.com/org/repo"))

    def test_schemeless_query_does_not_bypass_over_broad_check(self):
        self.assertTrue(is_over_broad_tracked_url("gemini.google.com/app?utm=1"))
        self.assertFalse(is_over_broad_tracked_url("gemini.google.com/app/abc123?utm=1"))


if __name__ == "__main__":
    unittest.main()
