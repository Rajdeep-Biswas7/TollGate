"""web_search: general web search. Uses Tavily when a key is set, else DuckDuckGo (no key)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..config import settings
from ..errors import ToolError
from ..net import client
from ..parsers import parse_ddg_html
from .base import Source, Tool, ToolOutput

_BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


class WebSearchArgs(BaseModel):
    query: str = Field(min_length=2, max_length=300, description="Search query, 2-12 words works best.")
    max_results: int = Field(default=5, ge=1, le=8, description="How many results to return.")


async def _tavily(query: str, n: int) -> list[dict]:
    r = await client().post(
        "https://api.tavily.com/search",
        json={"query": query, "max_results": n, "search_depth": "basic"},
        headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
    )
    if r.status_code in (401, 403):
        raise ToolError("Tavily rejected the API key. Check TAVILY_API_KEY in ai/.env.")
    r.raise_for_status()
    return [
        {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": (x.get("content") or "")[:400]}
        for x in r.json().get("results", [])
    ]


async def _duckduckgo(query: str, n: int) -> list[dict]:
    r = await client().post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": _BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"},
    )
    if r.status_code >= 400:
        raise ToolError(f"DuckDuckGo returned HTTP {r.status_code}.")
    return parse_ddg_html(r.text, n)


async def run(args: WebSearchArgs) -> ToolOutput:
    provider = "tavily" if settings.tavily_api_key else "duckduckgo"
    results = await (_tavily if provider == "tavily" else _duckduckgo)(args.query, args.max_results)
    if not results:
        raise ToolError(
            "No web results came back (the search provider may be rate limiting). "
            "Try wikipedia_lookup, hacker_news_search or search_papers, or rephrase the query."
        )
    return ToolOutput(
        data={"provider": provider, "query": args.query, "results": results},
        summary=f"{len(results)} results via {provider}",
        sources=[Source(r["title"] or r["url"], r["url"]) for r in results],
    )


TOOL = Tool(
    name="web_search",
    description=(
        "Search the open web for current information, news, docs and facts. Returns titles, URLs and "
        "snippets. Follow up with fetch_webpage to read a promising result in full."
    ),
    args_model=WebSearchArgs,
    handler=run,
)
