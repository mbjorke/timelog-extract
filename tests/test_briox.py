"""Tests for Briox connection test script security features."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import Request

import briox_connection_test as briox


class BrioxSecurityTests(unittest.TestCase):
    def test_http_json_rejects_plain_http(self):
        """http_json must raise ValueError for unsecure plain HTTP base URLs."""
        with self.assertRaises(ValueError) as ctx:
            briox.http_json("GET", "http://insecure.example.com/token")
        self.assertIn("must use HTTPS", str(ctx.exception))

    def test_http_json_allows_https(self):
        """http_json should accept secure HTTPS URLs."""
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = b'{"success": true}'
        mock_resp.status = 200

        with patch("briox_connection_test.urlopen", return_value=mock_resp) as mock_urlopen:
            status, payload = briox.http_json("GET", "https://secure.example.com/token")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"success": True})
            mock_urlopen.assert_called_once()

    def test_redirect_handler_rejects_http_redirect(self):
        """RejectHttpRedirectHandler must block redirects to plain HTTP."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/token")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://secure.example.test/token"
            )
        self.assertIn("non-HTTPS target rejected", str(ctx.exception))

    def test_redirect_handler_allows_https_redirect(self):
        """RejectHttpRedirectHandler should allow redirects to secure HTTPS on the same host."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/token")
        # Since Request redirect handling returns a new request object or delegates,
        # calling super().redirect_request with a dummy response might fail or succeed depending on input.
        # But we can verify it doesn't raise URLError.
        with patch("urllib.request.HTTPRedirectHandler.redirect_request", return_value="ok"):
            res = handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "https://secure.example.test/new-token"
            )
            self.assertEqual(res, "ok")

    def test_redirect_handler_rejects_cross_origin_https(self):
        """RejectHttpRedirectHandler must block redirects to a cross-origin HTTPS target."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/token")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "https://anotherhost.example.test/token"
            )
        self.assertIn("cross-origin HTTPS target rejected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
