"""Tests for security controls in the Briox API connection test."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

import briox_connection_test as bct


class BrioxSecurityTests(unittest.TestCase):
    def test_http_json_rejects_non_https(self):
        """http_json must raise ValueError for unsecure HTTP schemes."""
        with self.assertRaises(ValueError) as ctx:
            bct.http_json("GET", "http://api.briox.services/v2")
        self.assertIn("must use HTTPS", str(ctx.exception))

    def test_http_json_allows_https(self):
        """http_json should attempt request if scheme is HTTPS."""
        with patch.object(bct._briox_opener, "open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b"{}"
            mock_open.return_value.__enter__.return_value.status = 200

            status, payload = bct.http_json("GET", "https://api.briox.services/v2")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {})

    def test_briox_redirect_handler_rejects_http_redirect(self):
        """Briox opener rejects unsecure http redirects."""
        from core.http_security import RejectHttpRedirectHandler

        handler = RejectHttpRedirectHandler("Briox")
        req = Request("https://secure.example.test/v2")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://insecure.example.test"
            )
        self.assertIn("Briox redirect to insecure http:// rejected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
