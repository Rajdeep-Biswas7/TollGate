"""Google Gemini via the public REST API (function calling)."""
from __future__ import annotations

import httpx

from ..errors import LLMError
from ..schema import has_params
from ..tools.base import ToolSpec
from .retry import post_json
from .types import AssistantTurn, ToolCall, ToolResultItem

BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    provider = "gemini"

    def __init__(self, model: str, api_key: str, http: httpx.AsyncClient):
        self.model, self.api_key, self.http = model, api_key, http

    # --- history builders (provider-native shapes) ---
    def text_turn(self, role: str, text: str) -> dict:
        return {"role": "user" if role == "user" else "model", "parts": [{"text": text}]}

    def assistant_turn(self, turn: AssistantTurn) -> dict:
        return turn.raw  # replayed as-is, including any thought signatures

    def tool_results_turn(self, items: list[ToolResultItem]) -> dict:
        return {
            "role": "user",
            "parts": [
                {"functionResponse": {"name": it.call.name, "response": {"result": it.payload}}} for it in items
            ],
        }

    # --- model call ---
    async def generate(self, system: str, history: list, tools: list[ToolSpec], allow_tools: bool = True) -> AssistantTurn:
        declarations = []
        for t in tools:
            decl = {"name": t.name, "description": t.description}
            if has_params(t.parameters):  # Gemini rejects empty OBJECT schemas
                decl["parameters"] = t.parameters
            declarations.append(decl)
        body: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": history,
            "generationConfig": {"temperature": 0.3},
        }
        if declarations:
            body["tools"] = [{"functionDeclarations": declarations}]
            body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO" if allow_tools else "NONE"}}

        data = await post_json(
            self.http,
            f"{BASE}/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key, "content-type": "application/json"},
            body=body,
            provider="Gemini",
            model=self.model,
        )
        return self._parse(data)

    @staticmethod
    def _parse(data: dict) -> AssistantTurn:
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise LLMError("blocked", f"Gemini returned no answer{f' (blocked: {reason})' if reason else ''}. Try rephrasing.")
        cand = candidates[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if "text" in p and not p.get("thought"))
        calls = [
            ToolCall(id=fc.get("id") or f"call_{i}", name=fc.get("name", ""), args=fc.get("args") or {})
            for i, p in enumerate(parts)
            if (fc := p.get("functionCall"))
        ]
        if not text.strip() and not calls:
            raise LLMError("empty", f"Gemini returned an empty reply (finishReason={cand.get('finishReason', 'unknown')}). Try again.")
        usage = data.get("usageMetadata") or {}
        return AssistantTurn(
            text=text,
            tool_calls=calls,
            raw={"role": "model", "parts": parts},
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0),
        )
