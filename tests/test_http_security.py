"""Unit tests for core.http_security connection and redirect blocking."""

from __future__ import annotations

import unittest
from urllib.error import URLError
from urllib.request import Request

from core.http_security import RejectHttpRedirectHandler, build_https_opener


class HttpSecurityTests(unittest.TestCase):
    def test_http_request_interception(self):
        """Verify that RejectHttpRedirectHandler blocks initial plain HTTP requests."""
        handler = RejectHttpRedirectHandler("TestService")
        req = Request("http://insecure.example.test")
        with self.assertRaises(URLError) as ctx:
            handler.http_request(req)
        self.assertIn("TestService connection to insecure http:// rejected", str(ctx.exception))

    def test_redirect_request_rejection(self):
        """Verify that RejectHttpRedirectHandler blocks redirects to plain HTTP."""
        handler = RejectHttpRedirectHandler("TestService")
        req = Request("https://secure.example.test")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://insecure.example.test"
            )
        self.assertIn("TestService redirect to insecure http:// rejected", str(ctx.exception))

    def test_build_https_opener_blocks_http(self):
        """Verify that an opener built with build_https_opener rejects HTTP requests."""
        opener = build_https_opener("TestService")
        req = Request("http://insecure.example.test")
        with self.assertRaises(URLError) as ctx:
            opener.open(req)
        self.assertIn("TestService connection to insecure http:// rejected", str(ctx.exception))
