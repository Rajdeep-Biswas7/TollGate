"""One shared async HTTP client for tools and LLM calls."""
from __future__ import annotations

import httpx

USER_AGENT = "TollgateAgent/0.1 (research agent; hackathon project)"

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=8.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )
    return _client


async def close() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None
