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
                req, None, 301, "Moved Permanently", {}, "http://insecure.example.test"
            )
        self.assertIn("non-HTTPS target rejected", str(ctx.exception))

    def test_redirect_handler_rejects_ftp_redirect(self):
        """RejectHttpRedirectHandler must block redirects to FTP (non-HTTPS)."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/token")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "ftp://insecure.example.test"
            )
        self.assertIn("non-HTTPS target rejected", str(ctx.exception))

    def test_redirect_handler_rejects_cross_origin_https(self):
        """Same-scheme HTTPS redirects to another host must not carry Authorization."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://api.example.test/token")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req,
                None,
                301,
                "Moved Permanently",
                {},
                "https://evil.example.test/steal",
            )
        self.assertIn("cross-origin redirect rejected", str(ctx.exception))

    def test_redirect_handler_allows_same_origin_https_redirect(self):
        """Same-host HTTPS redirects are allowed (path-only moves)."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://secure.example.test/token")
        with patch("urllib.request.HTTPRedirectHandler.redirect_request", return_value="ok"):
            res = handler.redirect_request(
                req,
                None,
                301,
                "Moved Permanently",
                {},
                "https://secure.example.test/v2/token",
            )
            self.assertEqual(res, "ok")


if __name__ == "__main__":
    unittest.main()
