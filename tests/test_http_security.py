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


if __name__ == "__main__":
    unittest.main()
