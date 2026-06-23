"""Policy helpers for tracked_urls on multi-tenant AI chat hosts."""

from __future__ import annotations

from urllib.parse import urlparse

MULTI_TENANT_APP_HOSTS = frozenset(
    {
        "chat.openai.com",
        "chatgpt.com",
        "claude.ai",
        "gemini.google.com",
        "www.chat.openai.com",
        "www.chatgpt.com",
        "www.claude.ai",
        "www.gemini.google.com",
    }
)

_GENERIC_CHAT_ROUTE_SEGMENTS = frozenset({"app", "c", "chat", "g", "new", "share"})


def tracked_url_host_and_segments(raw: str) -> tuple[str, list[str]]:
    cleaned = str(raw or "").strip().lower().rstrip("/")
    if not cleaned:
        return "", []
    if "://" in cleaned:
        parsed = urlparse(cleaned)
        host = parsed.netloc.strip()
        path = parsed.path.strip("/")
    else:
        host, _, path = cleaned.partition("/")
    if host.startswith("www."):
        host = host[4:]
    segments = [segment for segment in path.split("/") if segment]
    return host, segments


def is_multi_tenant_tracked_url_host(raw: str) -> bool:
    host, _segments = tracked_url_host_and_segments(raw)
    return host in MULTI_TENANT_APP_HOSTS


def is_over_broad_tracked_url(raw: str) -> bool:
    """True when a tracked_urls entry would match unrelated chats on a shared host."""
    host, segments = tracked_url_host_and_segments(raw)
    if host not in MULTI_TENANT_APP_HOSTS:
        return False
    if not segments:
        return True
    if len(segments) == 1 and segments[0] in _GENERIC_CHAT_ROUTE_SEGMENTS:
        return True
    return False
