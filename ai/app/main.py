"""FastAPI app: /health, /models, /tools, and /run (Server-Sent Events)."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from . import __version__, net
from .agent import run_agent
from .config import settings
from .errors import LLMError
from .models import list_models
from .tools import ALL_TOOLS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tollgate")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class RunRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    model: str | None = Field(default=None, max_length=80)

    @field_validator("messages")
    @classmethod
    def last_must_be_user(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if v[-1].role != "user":
            raise ValueError("The last message must come from the user.")
        return v


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await net.close()


app = FastAPI(title="Tollgate AI service", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    models = list_models()
    return {
        "status": "ok",
        "version": __version__,
        "models_available": [m["id"] for m in models if m["available"]],
        "search_provider": "tavily" if settings.tavily_api_key else "duckduckgo",
        "tool_count": len(ALL_TOOLS),
    }


@app.get("/models")
async def models():
    return {"models": list_models()}


@app.get("/tools")
async def tools():
    out = []
    for t in ALL_TOOLS:
        spec = t.spec()
        out.append({"name": t.name, "description": t.description, "category": t.category, "parameters": spec.parameters})
    return {"tools": out}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/run")
async def run(req: RunRequest):
    async def stream():
        try:
            async for event in run_agent([m.model_dump() for m in req.messages], req.model, net.client()):
                yield _sse(event)
        except LLMError as exc:
            yield _sse({"type": "error", "code": exc.code, "message": exc.message})
        except Exception:  # never leak internals to the browser
            log.exception("agent run crashed")
            yield _sse({"type": "error", "code": "internal", "message": "Something went wrong inside the agent. Check the AI service logs."})
        yield _sse({"type": "done"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
