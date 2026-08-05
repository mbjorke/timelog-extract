"""Tests for HTTP security helpers and plain HTTP blocking handlers."""

import unittest
from urllib.error import URLError
from urllib.request import Request

from collectors.jira import _RejectHttpRedirectHandler
from core.http_security import RejectHttpRedirectHandler, build_https_opener


class HttpSecurityTests(unittest.TestCase):
    def test_reject_http_redirect_handler_blocks_initial_http(self):
        handler = RejectHttpRedirectHandler("MyService")
        req = Request("http://insecure.example.test/api")
        with self.assertRaises(URLError) as ctx:
            handler.http_request(req)
        self.assertIn("MyService request to insecure http:// rejected", str(ctx.exception))

    def test_reject_http_redirect_handler_blocks_http_redirect(self):
        handler = RejectHttpRedirectHandler("MyService")
        req = Request("https://secure.example.test/api")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://insecure.example.test/api"
            )
        self.assertIn("MyService redirect to insecure http:// rejected", str(ctx.exception))

    def test_jira_reject_handler_blocks_initial_http(self):
        handler = _RejectHttpRedirectHandler()
        req = Request("http://insecure.example.test/api")
        with self.assertRaises(URLError) as ctx:
            handler.http_request(req)
        self.assertIn("Jira request to insecure http:// rejected", str(ctx.exception))

    def test_jira_reject_handler_blocks_http_redirect(self):
        handler = _RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/api")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://insecure.example.test/api"
            )
        self.assertIn("Jira redirect to insecure http:// rejected", str(ctx.exception))

    def test_build_https_opener_blocks_http_request(self):
        opener = build_https_opener("TestService")
        req = Request("http://insecure.example.test/api")
        with self.assertRaises(URLError) as ctx:
            opener.open(req)
        self.assertIn("TestService request to insecure http:// rejected", str(ctx.exception))


class CollectorOpenerHttpRejectionTests(unittest.TestCase):
    """Each collector's own ``urlopen`` must refuse plain HTTP before sending.

    The handler tests above cover the shared helper in isolation; these go
    through the entry point the collectors actually call, so a collector that
    stops routing through the hardened opener fails here.
    """

    def test_github_opener_rejects_plain_http_request(self):
        from collectors.github import urlopen

        req = Request("http://insecure.example.test/users/u/events")
        with self.assertRaises(URLError) as ctx:
            urlopen(req)
        self.assertIn("GitHub request to insecure http:// rejected", str(ctx.exception))

    def test_jira_opener_rejects_plain_http_request(self):
        from collectors.jira import urlopen

        req = Request("http://insecure.example.test/rest/api/3/myself")
        with self.assertRaises(URLError) as ctx:
            urlopen(req)
        self.assertIn("Jira request to insecure http:// rejected", str(ctx.exception))

    def test_toggl_opener_rejects_plain_http_request(self):
        from collectors.toggl import urlopen

        req = Request("http://insecure.example.test/api/v9/me")
        with self.assertRaises(URLError) as ctx:
            urlopen(req)
        self.assertIn("Toggl request to insecure http:// rejected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
