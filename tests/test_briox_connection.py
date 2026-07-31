"""Tests for Briox connection test script security enforcement."""

import unittest
from urllib.error import URLError
from urllib.request import Request
from briox_connection_test import http_json


class BrioxConnectionSecurityTests(unittest.TestCase):
    def test_http_json_rejects_plain_http_url(self):
        """Verify that http_json rejects URLs that do not use the HTTPS scheme."""
        with self.assertRaises(ValueError) as ctx:
            http_json("GET", "http://api-fi.briox.services/v2/company/info")
        self.assertIn("must use HTTPS", str(ctx.exception))

    def test_http_json_accepts_https_url(self):
        """Verify that http_json accepts HTTPS URLs (though it might fail on actual connection)."""
        from unittest.mock import patch
        with patch("briox_connection_test._briox_opener.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b'{"data": "ok"}'
            mock_open.return_value.__enter__.return_value.status = 200

            status, payload = http_json("GET", "https://api-fi.briox.services/v2/company/info")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"data": "ok"})

    def test_briox_redirect_handler_rejects_http_redirect(self):
        """Verify that our RejectHttpRedirectHandler explicitly rejects redirects to unsecure http://."""
        from core.http_security import RejectHttpRedirectHandler

        handler = RejectHttpRedirectHandler("Briox")
        req = Request("https://api-fi.briox.services/v2/company/info")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://insecure.example.test"
            )
        self.assertIn("Briox redirect to insecure http:// rejected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
