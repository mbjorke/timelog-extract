"""Tests for secure Briox connection test client."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import Request

import briox_connection_test as briox_mod
from briox_connection_test import RejectHttpRedirectHandler, http_json


class BrioxConnectionSecurityTests(unittest.TestCase):
    def test_http_json_rejects_plain_http(self):
        """Verify that any unencrypted HTTP URL is immediately blocked with ValueError."""
        with patch.object(briox_mod, "_briox_opener") as mock_opener:
            with self.assertRaises(ValueError) as ctx:
                http_json("GET", "http://api.briox.services/v2/company/info")
            self.assertIn("must use HTTPS", str(ctx.exception))
            mock_opener.open.assert_not_called()

    def test_http_json_allows_https(self):
        """Verify that secure HTTPS URLs bypass validation and invoke the secure opener."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.status = 200

        with patch.object(briox_mod, "_briox_opener") as mock_opener:
            mock_opener.open.return_value = mock_response
            status, payload = http_json("GET", "https://api-se.briox.services/v2/company/info")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"status": "ok"})
            mock_opener.open.assert_called_once()

    def test_reject_http_redirect_handler_blocks_insecure_redirect(self):
        """Verify that RejectHttpRedirectHandler raises URLError when redirecting to plain HTTP."""
        handler = RejectHttpRedirectHandler()
        req = Request("https://api-se.briox.services/v2/company/info")

        # Test redirection to an insecure HTTP endpoint should raise URLError
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req=req,
                fp=None,
                code=302,
                msg="Found",
                headers={},
                newurl="http://malicious-intercept.com/info"
            )
        self.assertIn("rejected to protect credentials", str(ctx.exception))

    def test_reject_http_redirect_handler_allows_secure_redirect(self):
        """Verify that RejectHttpRedirectHandler allows redirects to secure HTTPS destinations."""
        handler = RejectHttpRedirectHandler()
        req = Request("https://api-se.briox.services/v2/company/info")

        # We need to mock the parent (super()) call or check that it doesn't raise URLError
        # calling super().redirect_request with dummy mock params might trigger internal urllib logic,
        # but we can verify it doesn't raise the URLError about insecure redirect.
        with patch("urllib.request.HTTPRedirectHandler.redirect_request") as mock_super:
            mock_super.return_value = "allowed_request"
            result = handler.redirect_request(
                req=req,
                fp=None,
                code=302,
                msg="Found",
                headers={},
                newurl="https://secure-target.briox.services/v2/company/info"
            )
            self.assertEqual(result, "allowed_request")
            mock_super.assert_called_once()


if __name__ == "__main__":
    unittest.main()
