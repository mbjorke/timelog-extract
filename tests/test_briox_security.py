"""Tests for the security controls in the standalone API connection test."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

import briox_connection_test as bct


class ApiConnectionSecurityTests(unittest.TestCase):
    def test_http_json_rejects_non_https(self):
        """http_json must raise ValueError for unsecure HTTP schemes."""
        with self.assertRaises(ValueError) as ctx:
            bct.http_json("GET", "http://api.example.test/v2")
        self.assertIn("must use HTTPS", str(ctx.exception))

    def test_http_json_allows_https(self):
        """http_json should attempt request if scheme is HTTPS."""
        with patch.object(bct._briox_opener, "open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b"{}"
            mock_open.return_value.__enter__.return_value.status = 200

            status, payload = bct.http_json("GET", "https://api.example.test/v2")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {})

    def test_redirect_handler_rejects_http_redirect(self):
        """The opener rejects unsecure http redirects."""
        from core.http_security import RejectHttpRedirectHandler

        handler = RejectHttpRedirectHandler("service-a")
        req = Request("https://secure.example.test/v2")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req, None, 301, "Moved Permanently", {}, "http://insecure.example.test"
            )
        self.assertIn("service-a redirect to insecure http:// rejected", str(ctx.exception))



class CrossHostRedirectTests(unittest.TestCase):
    """A redirect is a request to hand the Authorization header to someone else.

    Blocking only ``http://`` left the token exposed to any *other* HTTPS host a
    redirect could name: TLS protects it in transit but says nothing about
    whether the new host should receive it, and the redirect target is
    attacker-controlled once an endpoint is misconfigured or compromised.
    """

    def _handler(self):
        from core.http_security import RejectHttpRedirectHandler

        return RejectHttpRedirectHandler("service-a")

    def _redirect(self, from_url: str, to_url: str):
        return self._handler().redirect_request(
            Request(from_url), None, 301, "Moved Permanently", {}, to_url
        )

    def test_cross_host_https_redirect_is_rejected(self):
        with self.assertRaises(URLError) as ctx:
            self._redirect("https://api.example.test/v2", "https://elsewhere.example.test/v2")
        self.assertIn("different host", str(ctx.exception))

    def test_same_host_redirect_still_follows(self):
        with patch("urllib.request.HTTPRedirectHandler.redirect_request") as super_mock:
            super_mock.return_value = "followed"
            result = self._redirect("https://api.example.test/v2", "https://api.example.test/v2/token")
        self.assertEqual(result, "followed")

    def test_default_port_and_case_are_not_a_different_host(self):
        """Otherwise an explicit :443 or capitalised host would read as cross-origin."""
        with patch("urllib.request.HTTPRedirectHandler.redirect_request") as super_mock:
            super_mock.return_value = "followed"
            result = self._redirect("https://api.example.test/v2", "https://API.example.test:443/v2")
        self.assertEqual(result, "followed")

    def test_different_port_on_the_same_name_is_rejected(self):
        with self.assertRaises(URLError):
            self._redirect("https://api.example.test/v2", "https://api.example.test:8443/v2")

    def test_malformed_port_is_rejected(self):
        """origin_key's fail-closed branch: a port that will not parse.

        urlparse raises ValueError on `.port` here rather than returning None,
        so without the guard the comparison would raise out of the handler
        instead of refusing the redirect.
        """
        with self.assertRaises(URLError) as ctx:
            self._redirect(
                "https://api.example.test/v2",
                "https://api.example.test:not-a-port/v2",
            )
        self.assertIn("different host", str(ctx.exception))

    def test_malformed_port_does_not_match_another_malformed_port(self):
        """The sentinel carries the URL, so two unparseable targets stay distinct."""
        from core.http_security import origin_key

        self.assertNotEqual(
            origin_key("https://a.example.test:bad/v2"),
            origin_key("https://b.example.test:bad/v2"),
        )

    def test_plain_http_target_reports_the_scheme_not_the_host(self):
        """http:// must keep its own message — it is the more specific failure."""
        with self.assertRaises(URLError) as ctx:
            self._redirect("https://api.example.test/v2", "http://api.example.test/v2")
        self.assertIn("insecure http://", str(ctx.exception))


class JiraCrossHostRedirectTests(unittest.TestCase):
    """Jira builds its own opener, so it needs the same guard, not a similar one."""

    def test_cross_host_https_redirect_is_rejected(self):
        from collectors.jira import _RejectHttpRedirectHandler

        with self.assertRaises(URLError) as ctx:
            _RejectHttpRedirectHandler().redirect_request(
                Request("https://jira.example.test/rest/api/3/myself"),
                None, 301, "Moved Permanently", {},
                "https://elsewhere.example.test/rest/api/3/myself",
            )
        self.assertIn("different host", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
