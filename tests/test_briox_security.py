"""Tests for secure HTTPS connection checks in Briox connection tool."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request

# Ensure root folder is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import briox_connection_test as briox


class BrioxSecurityTests(unittest.TestCase):
    def test_http_json_rejects_plain_http_urls(self) -> None:
        """http_json must raise a ValueError if the URL does not use the HTTPS scheme."""
        with self.assertRaises(ValueError) as ctx:
            briox.http_json("GET", "http://api.briox.services/v2/company/info")
        self.assertIn("must use HTTPS", str(ctx.exception))

    def test_http_json_accepts_https_urls(self) -> None:
        """http_json should accept HTTPS URLs and proceed to call open (mocked or handled)."""
        # We can test that it doesn't fail on ValueError but raises standard connection/mocked errors if no mock
        # Let's mock _briox_opener.open to avoid actual network traffic
        from unittest.mock import MagicMock, patch

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = b'{"data": "success"}'
        mock_resp.status = 200

        with patch.object(briox._briox_opener, "open", return_value=mock_resp) as mock_open:
            status, payload = briox.http_json("GET", "https://api.briox.services/v2/company/info")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"data": "success"})
            mock_open.assert_called_once()

    def test_reject_http_redirect_handler_blocks_insecure_redirect(self) -> None:
        """RejectHttpRedirectHandler must block any redirect pointing to a plain HTTP URL."""
        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://api.briox.services/v2/company/info")

        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req,
                None,
                301,
                "Moved Permanently",
                {},
                "http://insecure-api.briox.services/v2/company/info",
            )
        self.assertIn("Briox redirect to insecure http:// rejected", str(ctx.exception))

    def test_reject_http_redirect_handler_allows_secure_redirect(self) -> None:
        """RejectHttpRedirectHandler should allow redirects pointing to HTTPS URLs."""
        # We can mock the super class's redirect_request to verify it's called
        from unittest.mock import patch

        handler = briox.RejectHttpRedirectHandler()
        req = Request("https://api.briox.services/v2/company/info")

        with patch("urllib.request.HTTPRedirectHandler.redirect_request") as mock_super_redirect:
            mock_super_redirect.return_value = "mocked_request"
            result = handler.redirect_request(
                req,
                None,
                301,
                "Moved Permanently",
                {},
                "https://secure-api.briox.services/v2/company/info",
            )
            self.assertEqual(result, "mocked_request")
            mock_super_redirect.assert_called_once_with(
                req,
                None,
                301,
                "Moved Permanently",
                {},
                "https://secure-api.briox.services/v2/company/info",
            )


if __name__ == "__main__":
    unittest.main()
