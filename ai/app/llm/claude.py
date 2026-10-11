"""Anthropic Claude via the Messages REST API (tool use)."""
from __future__ import annotations

import json

import httpx

from ..errors import LLMError
from ..tools.base import ToolSpec
from .retry import post_json
from .types import AssistantTurn, ToolCall, ToolResultItem

URL = "https://api.anthropic.com/v1/messages"


class ClaudeClient:
    provider = "anthropic"

    def __init__(self, model: str, api_key: str, http: httpx.AsyncClient):
        self.model, self.api_key, self.http = model, api_key, http

    def text_turn(self, role: str, text: str) -> dict:
        return {"role": "user" if role == "user" else "assistant", "content": text}

    def assistant_turn(self, turn: AssistantTurn) -> dict:
        return turn.raw

    def tool_results_turn(self, items: list[ToolResultItem]) -> dict:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": it.call.id,
                    "content": json.dumps(it.payload, ensure_ascii=False, default=str),
                    **({"is_error": True} if not it.payload.get("ok", True) else {}),
                }
                for it in items
            ],
        }

    async def generate(self, system: str, history: list, tools: list[ToolSpec], allow_tools: bool = True) -> AssistantTurn:
        body: dict = {
            "model": self.model,
            "max_tokens": 2048,
            "system": system,
            "messages": history,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters or {"type": "object", "properties": {}},
                }
                for t in tools
            ],
        }
        if not allow_tools:
            body["tool_choice"] = {"type": "none"}
        data = await post_json(
            self.http,
            URL,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            body=body,
            provider="Claude",
            model=self.model,
        )
        return self._parse(data)

    @staticmethod
    def _parse(data: dict) -> AssistantTurn:
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = [
            ToolCall(id=b["id"], name=b.get("name", ""), args=b.get("input") or {})
            for b in blocks
            if b.get("type") == "tool_use"
        ]
        if not text.strip() and not calls:
            raise LLMError("empty", f"Claude returned an empty reply (stop_reason={data.get('stop_reason', 'unknown')}). Try again.")
        usage = data.get("usage") or {}
        return AssistantTurn(
            text=text,
            tool_calls=calls,
            raw={"role": "assistant", "content": blocks},
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )
