"""Shared urllib helpers that keep credentials off insecure channels."""

from __future__ import annotations

from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, OpenerDirector, build_opener


class RejectHttpRedirectHandler(HTTPRedirectHandler):
    """Block redirects and initial requests to plain HTTP so Authorization headers are never forwarded."""

    def __init__(self, service: str = "API") -> None:
        super().__init__()
        self._service = service

    def http_request(self, req):
        """Intercept and reject any initial plain HTTP requests."""
        raise URLError(
            f"{self._service} connection to insecure http:// rejected to protect credentials"
        )

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if (urlparse(newurl).scheme or "").lower() == "http":
            raise URLError(
                f"{self._service} redirect to insecure http:// rejected to protect credentials"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_https_opener(service: str) -> OpenerDirector:
    """Return an opener that rejects ``http://`` redirects for *service*."""
    return build_opener(RejectHttpRedirectHandler(service), HTTPSHandler())
