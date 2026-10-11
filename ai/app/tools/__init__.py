"""Tool registry. Add a tool by creating a module with a TOOL object and listing it here."""
from __future__ import annotations

from . import calculator, clock, crypto, hacker_news, papers, wallet, web_search, webpage, wikipedia
from .base import Tool, ToolOutput, ToolRun, ToolSpec, Source, execute

ALL_TOOLS: list[Tool] = [
    web_search.TOOL,
    wikipedia.TOOL,
    papers.TOOL,
    webpage.TOOL,
    hacker_news.TOOL,
    crypto.TOOL,
    calculator.TOOL,
    clock.TOOL,
    wallet.TOOL,
]

_BY_NAME = {t.name: t for t in ALL_TOOLS}


def get_tool(name: str) -> Tool | None:
    return _BY_NAME.get(name)


__all__ = ["ALL_TOOLS", "get_tool", "execute", "Tool", "ToolOutput", "ToolRun", "ToolSpec", "Source"]
