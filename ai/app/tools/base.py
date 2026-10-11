"""Tool framework: a Tool couples a Pydantic args model with an async handler."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..config import settings
from ..errors import ToolError
from ..schema import clean_schema

log = logging.getLogger("tollgate.tools")

MAX_PREVIEW_CHARS = 4000  # what the UI inspector receives
MAX_LLM_CHARS = 9000  # what the model receives


@dataclass
class Source:
    title: str
    url: str

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url}


@dataclass
class ToolOutput:
    data: Any
    summary: str
    sources: list[Source] = field(default_factory=list)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict | None  # cleaned JSON schema, None when the tool takes no arguments


@dataclass
class ToolRun:
    ok: bool
    args: dict
    duration_ms: int
    summary: str
    output: ToolOutput | None = None
    error: str | None = None
    cached: bool = False

    def for_llm(self) -> dict:
        """JSON-able payload sent back to the model."""
        if not self.ok:
            return {"ok": False, "error": self.error}
        text = json.dumps(self.output.data, ensure_ascii=False, default=str)
        if len(text) > MAX_LLM_CHARS:
            return {"ok": True, "truncated": True, "result_preview": text[:MAX_LLM_CHARS]}
        return {"ok": True, "result": self.output.data}

    def preview(self) -> str:
        """Pretty JSON string for the UI's inspector."""
        body: Any = self.output.data if self.ok and self.output else {"error": self.error}
        text = json.dumps(body, ensure_ascii=False, indent=2, default=str)
        return text if len(text) <= MAX_PREVIEW_CHARS else text[:MAX_PREVIEW_CHARS] + "\n… (truncated)"


@dataclass
class Tool:
    name: str
    description: str
    args_model: Any  # a pydantic BaseModel subclass
    handler: Callable[[Any], Awaitable[ToolOutput]]
    category: str = "free"  # free | wallet

    def spec(self) -> ToolSpec:
        schema = clean_schema(self.args_model.model_json_schema())
        return ToolSpec(self.name, self.description, schema)


def _fmt_validation(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            parts = []
            for e in errors():
                loc = ".".join(str(x) for x in e.get("loc", ())) or "args"
                parts.append(f"{loc}: {e.get('msg', 'invalid')}")
            return "; ".join(parts)[:400]
        except Exception:  # pragma: no cover
            pass
    return str(exc)[:400]


async def execute(tool: Tool, raw_args: dict | None, timeout_s: float | None = None) -> ToolRun:
    """Validate args, run the handler with a timeout, never raise."""
    t0 = time.perf_counter()
    raw = raw_args if isinstance(raw_args, dict) else {}

    def elapsed() -> int:
        return int((time.perf_counter() - t0) * 1000)

    try:
        args = tool.args_model.model_validate(raw)
    except Exception as exc:
        msg = f"Invalid arguments: {_fmt_validation(exc)}"
        return ToolRun(False, raw, elapsed(), msg, error=msg)

    try:
        out = await asyncio.wait_for(tool.handler(args), timeout=timeout_s or settings.tool_timeout_s)
        return ToolRun(True, raw, elapsed(), out.summary, output=out)
    except ToolError as exc:
        return ToolRun(False, raw, elapsed(), str(exc), error=str(exc))
    except asyncio.TimeoutError:
        msg = "The tool timed out. Try a narrower request or a different tool."
        return ToolRun(False, raw, elapsed(), msg, error=msg)
    except Exception as exc:  # network errors, parse errors, bugs: report, don't crash the run
        log.exception("tool %s failed", tool.name)
        msg = f"The tool failed ({type(exc).__name__}). Try another approach."
        return ToolRun(False, raw, elapsed(), msg, error=msg)
