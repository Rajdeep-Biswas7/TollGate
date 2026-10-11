"""Network safety: block requests to private/internal addresses (SSRF guard).

The agent can be asked (or tricked by a web page) into fetching arbitrary URLs. We only allow
public http(s) hosts and re-check every redirect hop.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from .errors import ToolError


def ip_is_public(raw: str) -> bool:
    ip = ipaddress.ip_address(raw.split("%")[0])
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_url_shape(url: str) -> tuple[str, str, int]:
    """Return (scheme, hostname, port) or raise ToolError."""
    try:
        parsed = urlparse(url.strip())
    except ValueError as exc:
        raise ToolError("That does not look like a valid URL.") from exc
    if parsed.scheme not in ("http", "https"):
        raise ToolError("Only http:// and https:// URLs can be fetched.")
    host = parsed.hostname
    if not host:
        raise ToolError("The URL has no hostname.")
    if parsed.username or parsed.password:
        raise ToolError("URLs with embedded credentials are not allowed.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, host, port


async def assert_public_host(host: str, port: int) -> None:
    """Resolve the host and make sure every address is a public one."""
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ToolError(f"Could not resolve host '{host}'.") from exc
    if not infos:
        raise ToolError(f"Could not resolve host '{host}'.")
    for info in infos:
        if not ip_is_public(info[4][0]):
            raise ToolError("Blocked: that address is not on the public internet.")
