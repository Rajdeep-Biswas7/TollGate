"""hacker_news_search: tech news and community discussion (free, no key)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..errors import ToolError
from ..net import client
from .base import Source, Tool, ToolOutput


class HNArgs(BaseModel):
    query: str = Field(min_length=2, max_length=200, description="Keywords for tech, startup or crypto news.")
    max_results: int = Field(default=5, ge=1, le=8, description="How many stories to return.")


async def run(args: HNArgs) -> ToolOutput:
    r = await client().get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": args.query, "tags": "story", "hitsPerPage": args.max_results},
    )
    r.raise_for_status()
    stories = []
    for h in r.json().get("hits", []):
        discussion = f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        stories.append(
            {
                "title": h.get("title") or h.get("story_title") or "",
                "url": h.get("url") or discussion,
                "discussion": discussion,
                "points": h.get("points"),
                "comments": h.get("num_comments"),
                "date": (h.get("created_at") or "")[:10],
            }
        )
    if not stories:
        raise ToolError(f"No Hacker News stories matched '{args.query}'.")
    return ToolOutput(
        data={"query": args.query, "stories": stories},
        summary=f"{len(stories)} stories, top: {stories[0]['title'][:60]}",
        sources=[Source(s["title"] or s["url"], s["url"]) for s in stories],
    )


TOOL = Tool(
    name="hacker_news_search",
    description="Search Hacker News for tech, startup and crypto stories and what the community says about them.",
    args_model=HNArgs,
    handler=run,
)
