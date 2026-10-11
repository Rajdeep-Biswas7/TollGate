"""Test doubles: a fake HTTP client and a scripted LLM client."""
from __future__ import annotations

from app.llm.types import AssistantTurn, ToolCall


class FakeResponse:
    def __init__(self, status=200, json_data=None, text="", headers=None, body=b"", encoding="utf-8"):
        self.status_code = status
        self._json = json_data
        self.text = text
        self.headers = headers or {}
        self._body = body
        self.encoding = encoding

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    async def aiter_bytes(self):
        yield self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class FakeHttp:
    """Maps URL substrings to canned responses; records calls."""

    def __init__(self, routes: dict[str, FakeResponse]):
        self.routes, self.calls = routes, []

    def _match(self, url):
        for key, resp in self.routes.items():
            if key in url:
                return resp
        raise AssertionError(f"unexpected URL {url}")

    async def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self._match(url)

    async def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self._match(url)

    def stream(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self._match(url)


class ScriptedLLM:
    """Plays back a list of AssistantTurns and records every generate() call."""

    provider = "fake"

    def __init__(self, turns):
        self.turns, self.calls = list(turns), []

    def text_turn(self, role, text):
        return {"role": role, "text": text}

    def assistant_turn(self, turn):
        return {"role": "assistant", "calls": [c.name for c in turn.tool_calls], "text": turn.text}

    def tool_results_turn(self, items):
        return {"role": "tool", "results": [(i.call.name, i.payload) for i in items]}

    async def generate(self, system, history, tools, allow_tools=True):
        self.calls.append({"system": system, "history": list(history), "tools": len(tools), "allow_tools": allow_tools})
        return self.turns.pop(0)


def call(name, args, id_="c1"):
    return ToolCall(id=id_, name=name, args=args)


def turn(text="", calls=()):
    return AssistantTurn(text=text, tool_calls=list(calls), raw={"raw": True}, input_tokens=10, output_tokens=5)
