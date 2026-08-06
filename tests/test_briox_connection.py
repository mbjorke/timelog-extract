"""Tests for the Briox connection test script security enhancements."""

from __future__ import annotations

import unittest
from urllib.error import URLError
from urllib.request import Request

from briox_connection_test import RejectHttpRedirectHandler, http_json


class BrioxConnectionSecurityTests(unittest.TestCase):
    def test_reject_http_redirect_blocks_unsecure_redirect(self):
        handler = RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/api")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req,
                None,
                301,
                "Moved Permanently",
                {},
                "http://insecure.example.test/api",
            )
        self.assertIn("Briox redirect to insecure http:// rejected", str(ctx.exception))

    def test_reject_http_redirect_allows_secure_redirect(self):
        handler = RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/api")
        res = handler.redirect_request(
            req,
            None,
            301,
            "Moved Permanently",
            {},
            "https://another-secure.example.test/api",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res.get_full_url(), "https://another-secure.example.test/api")

    def test_http_json_rejects_non_https(self):
        with self.assertRaises(ValueError) as ctx:
            http_json("GET", "http://insecure.example.test/api")
        self.assertIn("must use HTTPS", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
