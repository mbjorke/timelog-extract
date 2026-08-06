"""Shared urllib helpers that keep credentials off insecure channels."""

from __future__ import annotations

from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, OpenerDirector, build_opener

_DEFAULT_PORTS = {"https": 443, "http": 80}


def origin_key(url: str) -> tuple:
    """Normalized ``(host, port)`` for comparing redirect targets.

    Case and an explicitly written default port must not read as a different
    host, or ``https://api.example:443`` → ``https://API.example`` would be
    rejected as cross-origin. A malformed port yields a sentinel that matches
    nothing, so it fails closed rather than comparing equal by accident.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    try:
        port = parsed.port
    except ValueError:
        return ("<invalid>", url)
    return ((parsed.hostname or "").lower(), port or _DEFAULT_PORTS.get(scheme))


class RejectHttpRedirectHandler(HTTPRedirectHandler):
    """Keep credential-bearing requests on the exact origin they were aimed at.

    urllib follows redirects and re-sends the request's headers, so a redirect
    is a request to hand the ``Authorization`` header to whoever the response
    names. Two things are therefore refused:

    - a target on plain ``http://`` — the token would cross the wire in clear;
    - a target on a *different host*, even over HTTPS — TLS protects the token
      in transit but says nothing about whether the new host should receive it,
      and a redirect is attacker-controlled input whenever the endpoint is
      misconfigured or compromised.

    Same-origin redirects (path or query changes) still follow normally, which
    covers the legitimate cases. This repo's integrations address fixed, known
    endpoints — the Briox region variants in ``briox_connection_test.py`` are
    tried explicitly as separate base URLs, not reached via redirects — so no
    supported flow depends on a cross-host hop.
    """

    def __init__(self, service: str = "API") -> None:
        super().__init__()
        self._service = service

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if (urlparse(newurl).scheme or "").lower() == "http":
            raise URLError(
                f"{self._service} redirect to insecure http:// rejected to protect credentials"
            )
        if origin_key(newurl) != origin_key(req.full_url):
            raise URLError(
                f"{self._service} redirect to a different host "
                f"({urlparse(newurl).hostname!r}) rejected to protect credentials"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_https_opener(service: str) -> OpenerDirector:
    """Return an opener that keeps *service* credentials on their own origin."""
    return build_opener(RejectHttpRedirectHandler(service), HTTPSHandler())
