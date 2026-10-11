"""The agent loop: LLM <-> tools, emitting events for the UI as it goes."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from typing import AsyncIterator

import httpx

from .config import Settings, settings as default_settings
from .errors import LLMError
from .llm import make_client
from .llm.types import ToolResultItem, Usage
from .models import resolve_model
from .prompts import FORCE_FINAL_SUFFIX, build_system_prompt
from .tools import ALL_TOOLS, ToolRun, execute, get_tool
from .tools.base import Source

_CONF = re.compile(r"^[ \t]*[*_#>\-]*[ \t]*confidence[ \t]*[*_]*[ \t]*:[ \t]*[*_]*[ \t]*(high|medium|low)\b[^\n]*$", re.I | re.M)
_GAP = re.compile(r"^[ \t]*[*_#>\-]*[ \t]*premium gap[ \t]*[*_]*[ \t]*:[ \t]*[*_]*[ \t]*(.+?)[ \t]*[*_]*[ \t]*$", re.I | re.M)
_NONE_WORDS = {"none", "none.", "n/a", "no", "no.", "nothing", "-"}


def parse_footer(text: str) -> tuple[str, str | None, str | None]:
    """Pull the 'Confidence:' and 'Premium gap:' lines out of the answer."""
    confidence = None
    gap = None
    m = _CONF.search(text)
    if m:
        confidence = m.group(1).lower()
        text = text[: m.start()] + text[m.end():]
    g = _GAP.search(text)
    if g:
        value = g.group(1).strip().strip('"').strip()
        gap = None if value.lower() in _NONE_WORDS else value
        text = text[: g.start()] + text[g.end():]
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, confidence, gap


def _call_key(name: str, args: dict) -> str:
    return name + ":" + json.dumps(args, sort_keys=True, default=str)


async def run_agent(
    messages: list[dict],
    model_id: str | None,
    http: httpx.AsyncClient,
    s: Settings = default_settings,
    client_factory=make_client,
) -> AsyncIterator[dict]:
    """Yield UI events. Raises LLMError for model problems (the caller turns it into an error event)."""
    t0 = time.perf_counter()
    run_id = uuid.uuid4().hex[:12]
    spec = resolve_model(model_id, s)
    client = client_factory(spec, http)
    yield {"type": "run_started", "run_id": run_id, "model": spec.id, "provider": spec.provider, "label": spec.label}

    # Drop leading assistant messages: both providers require the conversation to start with the user.
    msgs = list(messages)
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    history = [client.text_turn(m["role"], m["content"]) for m in msgs]

    specs = [t.spec() for t in ALL_TOOLS]
    system = build_system_prompt()
    usage = Usage()
    sources: dict[str, dict] = {}
    tools_used: list[str] = []
    cache: dict[str, ToolRun] = {}
    tool_calls_made = 0
    final_text = ""

    for step in range(1, s.max_steps + 1):
        yield {"type": "status", "message": "Thinking…" if step == 1 else "Reading what the tools found…"}
        turn = await client.generate(system, history, specs)
        usage.add(turn)

        if not turn.tool_calls:
            final_text = turn.text
            break

        history.append(client.assistant_turn(turn))
        if turn.text.strip():
            yield {"type": "note", "text": turn.text.strip()[:500]}

        # announce, then run all requested tools in parallel
        for c in turn.tool_calls:
            yield {"type": "tool_call", "id": f"{step}:{c.id}", "name": c.name, "args": c.args, "step": step}

        async def _run_one(call):
            tool = get_tool(call.name)
            if tool is None:
                msg = f"Unknown tool '{call.name}'. Available: {', '.join(t.name for t in ALL_TOOLS)}."
                return call, ToolRun(False, call.args, 0, msg, error=msg)
            key = _call_key(call.name, call.args)
            if key in cache:
                hit = cache[key]
                return call, ToolRun(hit.ok, hit.args, 0, hit.summary, hit.output, hit.error, cached=True)
            run = await execute(tool, call.args, s.tool_timeout_s)
            cache[key] = run
            return call, run

        tasks = [asyncio.create_task(_run_one(c)) for c in turn.tool_calls]
        done: dict[str, ToolRun] = {}
        for fut in asyncio.as_completed(tasks):
            call, run = await fut
            done[call.id] = run
            tool_calls_made += 1
            tools_used.append(call.name)
            new_sources = []
            if run.ok and run.output:
                for src in run.output.sources:
                    if src.url and src.url not in sources:
                        sources[src.url] = {**src.to_dict(), "tool": call.name}
                        new_sources.append(sources[src.url])
            yield {
                "type": "tool_result",
                "id": f"{step}:{call.id}",
                "name": call.name,
                "ok": run.ok,
                "summary": run.summary,
                "output": run.preview(),
                "duration_ms": run.duration_ms,
                "cached": run.cached,
                "sources": new_sources,
            }
        history.append(client.tool_results_turn([ToolResultItem(c, done[c.id].for_llm()) for c in turn.tool_calls]))
    else:
        # Tool budget exhausted: ask for a final answer with tools switched off.
        yield {"type": "status", "message": "Writing the answer…"}
        turn = await client.generate(system + FORCE_FINAL_SUFFIX, history, specs, allow_tools=False)
        usage.add(turn)
        final_text = turn.text

    if not final_text.strip():
        raise LLMError("empty", "The model did not produce an answer. Please try again.")

    text, confidence, gap = parse_footer(final_text)
    yield {
        "type": "final",
        "text": text,
        "confidence": confidence,
        "premium_gap": gap,
        "sources": list(sources.values()),
        "stats": {
            "steps": step,
            "tool_calls": tool_calls_made,
            "tools_used": sorted(set(tools_used)),
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "paid_calls": 0,
            "cost_usdc": 0.0,
        },
    }
