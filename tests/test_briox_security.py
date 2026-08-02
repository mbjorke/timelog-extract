"""Tests for secure HTTPS and redirect handling in Briox API connection test."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import Request

import briox_connection_test


class BrioxSecurityTests(unittest.TestCase):
    def test_http_json_rejects_plain_http(self):
        # Ensure that non-HTTPS URLs are immediately rejected with ValueError.
        with self.assertRaises(ValueError) as context:
            briox_connection_test.http_json("GET", "http://api.briox.services/v2/token")

        self.assertIn("must use HTTPS", str(context.exception))

    def test_http_json_allows_https(self):
        # Mock the opener to avoid actual network request
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.status = 200

        with patch.object(briox_connection_test._briox_opener, "open", return_value=mock_resp) as mock_open:
            status, payload = briox_connection_test.http_json("GET", "https://api.briox.services/v2/token")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"status": "ok"})
            mock_open.assert_called_once()

    def test_redirect_handler_blocks_insecure_redirect(self):
        handler = briox_connection_test.RejectHttpRedirectHandler()
        req = Request("https://api.briox.services/v2/token")

        with self.assertRaises(URLError) as context:
            handler.redirect_request(
                req,
                fp=None,
                code=301,
                msg="Moved Permanently",
                headers={},
                newurl="http://malicious.site.com/token"
            )

        self.assertIn("redirect to insecure http:// rejected", str(context.exception))

    def test_redirect_handler_allows_secure_redirect(self):
        handler = briox_connection_test.RejectHttpRedirectHandler()
        req = Request("https://api.briox.services/v2/token")

        # We can mock the parent class's redirect_request to verify it's called
        with patch("urllib.request.HTTPRedirectHandler.redirect_request") as mock_super_redirect:
            handler.redirect_request(
                req,
                fp=None,
                code=301,
                msg="Moved Permanently",
                headers={},
                newurl="https://api-se.briox.services/v2/token"
            )
            mock_super_redirect.assert_called_once_with(
                req, None, 301, "Moved Permanently", {}, "https://api-se.briox.services/v2/token"
            )


if __name__ == "__main__":
    unittest.main()
