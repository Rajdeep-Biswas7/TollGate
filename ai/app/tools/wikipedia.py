"""wikipedia_lookup: encyclopedia summaries (free, no key)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..errors import ToolError
from ..net import client
from .base import Source, Tool, ToolOutput


class WikipediaArgs(BaseModel):
    query: str = Field(min_length=2, max_length=200, description="Topic, person, place or concept to look up.")
    max_results: int = Field(default=3, ge=1, le=5, description="How many matching articles to return.")


async def run(args: WikipediaArgs) -> ToolOutput:
    r = await client().get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": args.query,
            "gsrlimit": args.max_results,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "exlimit": args.max_results,
            "inprop": "url",
            "redirects": 1,
        },
    )
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    ordered = sorted(pages.values(), key=lambda p: p.get("index", 99))
    articles = [
        {
            "title": p.get("title", ""),
            "summary": (p.get("extract") or "")[:1400],
            "url": p.get("fullurl") or f"https://en.wikipedia.org/?curid={p.get('pageid')}",
        }
        for p in ordered
    ]
    if not articles:
        raise ToolError(f"No Wikipedia article matched '{args.query}'. Try different keywords.")
    return ToolOutput(
        data={"query": args.query, "articles": articles},
        summary=f"{len(articles)} articles, top: {articles[0]['title']}",
        sources=[Source(a["title"], a["url"]) for a in articles],
    )


TOOL = Tool(
    name="wikipedia_lookup",
    description="Look up background knowledge on a topic, person, place or concept from Wikipedia (intro summaries).",
    args_model=WikipediaArgs,
    handler=run,
)
