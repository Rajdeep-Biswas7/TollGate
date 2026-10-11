"""search_papers: scientific preprints from arXiv (free, no key)."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..errors import ToolError
from ..net import client
from ..parsers import parse_arxiv_atom
from .base import Source, Tool, ToolOutput


class PapersArgs(BaseModel):
    query: str = Field(min_length=2, max_length=200, description="Topic keywords, e.g. 'retrieval augmented generation'.")
    max_results: int = Field(default=5, ge=1, le=8, description="How many papers to return.")


async def run(args: PapersArgs) -> ToolOutput:
    words = re.findall(r"[A-Za-z0-9\-]+", args.query)[:6]
    if not words:
        raise ToolError("Give at least one keyword to search for.")
    r = await client().get(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": " AND ".join(f"all:{w}" for w in words),
            "start": 0,
            "max_results": args.max_results,
            "sortBy": "relevance",
        },
    )
    r.raise_for_status()
    papers = parse_arxiv_atom(r.text)
    if not papers:
        raise ToolError(f"No arXiv papers matched '{args.query}'. Try fewer or broader keywords.")
    return ToolOutput(
        data={"query": args.query, "papers": papers},
        summary=f"{len(papers)} papers, top: {papers[0]['title'][:60]}",
        sources=[Source(p["title"], p["url"]) for p in papers],
    )


TOOL = Tool(
    name="search_papers",
    description="Search arXiv for research papers on a topic. Returns title, authors, date, abstract and link.",
    args_model=PapersArgs,
    handler=run,
)
