"""fetch_webpage: read a public web page as clean text (SSRF-guarded)."""
from __future__ import annotations

from urllib.parse import urljoin

from pydantic import BaseModel, Field

from ..errors import ToolError
from ..net import client
from ..parsers import html_to_text
from ..safety import assert_public_host, validate_url_shape
from .base import Source, Tool, ToolOutput

MAX_BYTES = 1_500_000
MAX_HOPS = 4
_TEXT_TYPES = ("text/html", "application/xhtml", "text/plain", "application/json", "text/markdown", "application/xml", "text/xml")


class FetchArgs(BaseModel):
    url: str = Field(min_length=8, max_length=2000, description="Full http(s) URL of the page to read.")
    max_chars: int = Field(default=6000, ge=500, le=12000, description="Maximum characters of page text to return.")


async def run(args: FetchArgs) -> ToolOutput:
    url = args.url.strip()
    for _hop in range(MAX_HOPS):
        _scheme, host, port = validate_url_shape(url)
        await assert_public_host(host, port)  # re-checked on every redirect hop
        async with client().stream("GET", url, follow_redirects=False, headers={"Accept": "text/html,text/plain,*/*;q=0.5"}) as r:
            if r.status_code in (301, 302, 303, 307, 308):
                location = r.headers.get("location")
                if not location:
                    raise ToolError("The site redirected without a destination.")
                url = urljoin(url, location)
                continue
            if r.status_code >= 400:
                raise ToolError(f"The page returned HTTP {r.status_code}.")
            ctype = (r.headers.get("content-type") or "").lower()
            if "pdf" in ctype:
                raise ToolError("PDFs are not supported yet. Use search_papers for abstracts or try an HTML source.")
            if ctype and not any(t in ctype for t in _TEXT_TYPES):
                raise ToolError(f"Unsupported content type: {ctype.split(';')[0]}.")
            chunks, size = [], 0
            async for chunk in r.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    break
            body = b"".join(chunks)[:MAX_BYTES]
            encoding = r.encoding or "utf-8"
        text = body.decode(encoding, errors="replace")
        if "html" in ctype or text.lstrip().lower().startswith(("<!doctype", "<html")):
            title, content = html_to_text(text)
        else:
            title, content = "", text.strip()
        if not content:
            raise ToolError("The page had no readable text (it may need JavaScript).")
        truncated = len(content) > args.max_chars
        content = content[: args.max_chars]
        return ToolOutput(
            data={"url": url, "title": title, "text": content, "truncated": truncated},
            summary=f"read {len(content)} chars from {host}",
            sources=[Source(title or host, url)],
        )
    raise ToolError("Too many redirects.")


TOOL = Tool(
    name="fetch_webpage",
    description=(
        "Download a public web page and return its readable text. Use it to read a result from web_search "
        "in full. Cannot read PDFs, login-only pages or JavaScript-only pages."
    ),
    args_model=FetchArgs,
    handler=run,
)
