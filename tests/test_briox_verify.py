"""Tests for Briox standalone connection test security enforcement."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import Request

import briox_connection_test as briox


class BrioxSecurityVerifyTests(unittest.TestCase):
    def test_http_json_rejects_plain_http(self):
        """Initial URL scheme must be HTTPS to prevent token leakage."""
        with self.assertRaises(ValueError) as ctx:
            briox.http_json("GET", "http://insecure-api.briox.services/v2/company/info")
        self.assertIn("must use HTTPS", str(ctx.exception))

    def test_redirect_handler_blocks_insecure_redirect(self):
        """HTTPRedirectHandler rejects redirection to plain HTTP schemes."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://api-se.briox.services/v2/company/info")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://insecure-target.test/v2"
            )
        self.assertIn("redirect to insecure http:// rejected", str(ctx.exception))

    def test_http_json_allows_https(self):
        """HTTPS scheme goes through and requests using the customized opener."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "ok"}'

        with patch.object(briox._briox_opener, "open", return_value=mock_response) as mock_open:
            status, payload = briox.http_json("GET", "https://api-se.briox.services/v2/company/info")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"status": "ok"})
            mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
