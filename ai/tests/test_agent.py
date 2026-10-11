import unittest
from unittest import mock

from tests import _stubs  # noqa: F401
from tests.fakes import FakeHttp, FakeResponse, ScriptedLLM, call, turn

from app import agent as agent_mod
from app.agent import parse_footer, run_agent
from app.config import Settings
from app.errors import LLMError
from app.llm.claude import ClaudeClient
from app.llm.gemini import GeminiClient
from app.llm.types import ToolResultItem
from app.models import list_models, resolve_model
from app.tools.base import Source, Tool, ToolOutput
from app.tools.calculator import CalcArgs

S = Settings(gemini_api_key="g-key", anthropic_api_key="")


async def collect(gen):
    return [e async for e in gen]


class FooterTests(unittest.TestCase):
    def test_parse(self):
        text, conf, gap = parse_footer("Answer here.\n\nConfidence: High\nPremium gap: A paid on-chain analytics feed")
        self.assertEqual((text, conf, gap), ("Answer here.", "high", "A paid on-chain analytics feed"))
        text, conf, gap = parse_footer("Ans\n**Confidence:** Medium\n**Premium gap:** none")
        self.assertEqual((text, conf, gap), ("Ans", "medium", None))
        text, conf, gap = parse_footer("Just an answer, no footer.")
        self.assertEqual((text, conf, gap), ("Just an answer, no footer.", None, None))
        text, _, _ = parse_footer("I have high confidence in this.\nConfidence: Low")
        self.assertEqual(text, "I have high confidence in this.")


class ModelTests(unittest.TestCase):
    def test_resolve(self):
        self.assertEqual(resolve_model(None, S).id, "gemini-flash-latest")
        self.assertEqual(resolve_model("gemini-2.5-flash", S).provider, "gemini")
        self.assertEqual(resolve_model("gemini-9-future", S).provider, "gemini")  # unknown but plausible ids pass
        with self.assertRaises(LLMError) as cm:
            resolve_model("claude-haiku-4-5-20251001", S)
        self.assertEqual(cm.exception.code, "no_key")
        for bad in ["../../etc", "gpt-4", "gemini flash", "a" * 100]:
            with self.assertRaises(LLMError, msg=bad):
                resolve_model(bad, S)
        with self.assertRaises(LLMError):
            resolve_model(None, Settings())
        avail = {m["id"]: m["available"] for m in list_models(S)}
        self.assertTrue(avail["gemini-flash-latest"])
        self.assertFalse(avail["claude-sonnet-5-5"])


class LoopTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        async def fake_search(args):
            return ToolOutput({"hits": [args.expression]}, "found it", [Source("Doc", "https://doc.example/1")])

        self.tool = Tool("calculator", "d", CalcArgs, fake_search)
        p1 = mock.patch.object(agent_mod, "ALL_TOOLS", [self.tool])
        p2 = mock.patch.object(agent_mod, "get_tool", lambda n: self.tool if n == "calculator" else None)
        p1.start(); p2.start()
        self.addCleanup(p1.stop); self.addCleanup(p2.stop)

    def run_with(self, turns, messages=None, s=S):
        llm = ScriptedLLM(turns)
        msgs = messages or [{"role": "user", "content": "hi"}]
        events = collect(run_agent(msgs, None, object(), s, client_factory=lambda spec, http: llm))
        return llm, events

    async def test_direct_answer(self):
        llm, ev = self.run_with([turn("Hello!\nConfidence: High\nPremium gap: none")])
        events = await ev
        self.assertEqual([e["type"] for e in events], ["run_started", "status", "final"])
        final = events[-1]
        self.assertEqual(final["text"], "Hello!")
        self.assertEqual(final["confidence"], "high")
        self.assertEqual(final["stats"]["tool_calls"], 0)
        self.assertEqual(final["stats"]["cost_usdc"], 0.0)

    async def test_tool_round_trip_collects_sources_and_dedupes(self):
        turns = [
            turn("let me check", [call("calculator", {"expression": "1+1"}, "a"), call("calculator", {"expression": "1+1"}, "b"), call("nope", {}, "c")]),
            turn("It is 2.\nConfidence: High"),
        ]
        llm, ev = self.run_with(turns)
        events = await ev
        types = [e["type"] for e in events]
        self.assertEqual(types[:4], ["run_started", "status", "note", "tool_call"])
        results = [e for e in events if e["type"] == "tool_result"]
        self.assertEqual(len(results), 3)
        by_id = {r["id"].split(":", 1)[1]: r for r in results}
        self.assertTrue(by_id["a"]["ok"] or by_id["b"]["ok"])
        self.assertFalse(by_id["c"]["ok"])
        self.assertIn("Unknown tool", by_id["c"]["summary"])
        self.assertEqual(sum(1 for r in results if r["cached"]), 1)  # identical call served from cache
        final = events[-1]
        self.assertEqual(final["sources"], [{"title": "Doc", "url": "https://doc.example/1", "tool": "calculator"}])
        self.assertEqual(final["stats"]["tool_calls"], 3)
        # second model call saw one tool-results turn with all three results, in order
        hist = llm.calls[1]["history"]
        self.assertEqual(hist[-1]["role"], "tool")
        self.assertEqual([n for n, _ in hist[-1]["results"]], ["calculator", "calculator", "nope"])

    async def test_leading_assistant_messages_are_dropped(self):
        msgs = [{"role": "assistant", "content": "welcome"}, {"role": "user", "content": "q"}]
        llm, ev = self.run_with([turn("ok")], msgs)
        await ev
        self.assertEqual(llm.calls[0]["history"], [{"role": "user", "text": "q"}])

    async def test_budget_exhaustion_forces_final_answer(self):
        s = Settings(gemini_api_key="g", max_steps=2)
        turns = [turn("", [call("calculator", {"expression": "1"}, "a")]), turn("", [call("calculator", {"expression": "2"}, "b")]), turn("Best effort.")]
        llm, ev = self.run_with(turns, s=s)
        events = await ev
        self.assertEqual(events[-1]["text"], "Best effort.")
        self.assertFalse(llm.calls[-1]["allow_tools"])
        self.assertIn("tool budget", llm.calls[-1]["system"])

    async def test_empty_final_raises(self):
        _, ev = self.run_with([turn("   ")])
        with self.assertRaises(LLMError):
            await ev

    async def test_missing_key_raises_before_any_event(self):
        with self.assertRaises(LLMError) as cm:
            await collect(run_agent([{"role": "user", "content": "x"}], None, object(), Settings(), client_factory=lambda *a: None))
        self.assertEqual(cm.exception.code, "no_key")


class ProviderFormatTests(unittest.IsolatedAsyncioTestCase):
    def test_gemini_parse_and_history(self):
        data = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "thinking out loud"}, {"functionCall": {"name": "calculator", "args": {"expression": "1+1"}}, "thoughtSignature": "sig"}]}}],
            "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 4},
        }
        t = GeminiClient._parse(data)
        self.assertEqual(t.text, "thinking out loud")
        self.assertEqual((t.tool_calls[0].name, t.tool_calls[0].args), ("calculator", {"expression": "1+1"}))
        self.assertEqual((t.input_tokens, t.output_tokens), (11, 4))
        self.assertEqual(t.raw["parts"][1]["thoughtSignature"], "sig")  # replayed verbatim
        c = GeminiClient("m", "k", None)
        tr = c.tool_results_turn([ToolResultItem(t.tool_calls[0], {"ok": True, "result": 2})])
        self.assertEqual(tr["role"], "user")
        self.assertEqual(tr["parts"][0]["functionResponse"]["name"], "calculator")
        with self.assertRaises(LLMError):
            GeminiClient._parse({"candidates": []})
        with self.assertRaises(LLMError):
            GeminiClient._parse({"candidates": [{"finishReason": "SAFETY"}]})

    async def test_gemini_request_body(self):
        from app.tools import ALL_TOOLS

        captured = {}

        class Http:
            async def post(self, url, headers=None, json=None, timeout=None):
                captured.update(url=url, headers=headers, body=json)
                return FakeResponse(json_data={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

        c = GeminiClient("gemini-flash-latest", "KEY", Http())
        await c.generate("sys", [c.text_turn("user", "hi")], [t.spec() for t in ALL_TOOLS], allow_tools=False)
        self.assertTrue(captured["url"].endswith("/models/gemini-flash-latest:generateContent"))
        self.assertEqual(captured["headers"]["x-goog-api-key"], "KEY")
        decls = captured["body"]["tools"][0]["functionDeclarations"]
        wallet = next(d for d in decls if d["name"] == "get_wallet_info")
        self.assertNotIn("parameters", wallet)  # Gemini rejects empty object schemas
        self.assertIn("parameters", next(d for d in decls if d["name"] == "calculator"))
        self.assertEqual(captured["body"]["toolConfig"]["functionCallingConfig"]["mode"], "NONE")

    def test_claude_parse_and_history(self):
        data = {
            "content": [{"type": "text", "text": "hm"}, {"type": "tool_use", "id": "toolu_1", "name": "calculator", "input": {"expression": "2*2"}}],
            "usage": {"input_tokens": 20, "output_tokens": 8},
            "stop_reason": "tool_use",
        }
        t = ClaudeClient._parse(data)
        self.assertEqual(t.tool_calls[0].id, "toolu_1")
        self.assertEqual(t.raw, {"role": "assistant", "content": data["content"]})
        c = ClaudeClient("m", "k", None)
        tr = c.tool_results_turn([ToolResultItem(t.tool_calls[0], {"ok": False, "error": "boom"})])
        block = tr["content"][0]
        self.assertEqual((block["type"], block["tool_use_id"], block.get("is_error")), ("tool_result", "toolu_1", True))

    async def test_claude_request_body_and_error_mapping(self):
        from app.llm.retry import post_json

        captured = {}

        class Http:
            async def post(self, url, headers=None, json=None, timeout=None):
                captured.update(url=url, headers=headers, body=json)
                return FakeResponse(json_data={"content": [{"type": "text", "text": "ok"}], "usage": {}})

        c = ClaudeClient("claude-haiku-4-5-20251001", "KEY", Http())
        from app.tools import ALL_TOOLS

        await c.generate("sys", [c.text_turn("user", "hi")], [t.spec() for t in ALL_TOOLS], allow_tools=False)
        self.assertEqual(captured["headers"]["x-api-key"], "KEY")
        self.assertEqual(captured["body"]["tool_choice"], {"type": "none"})
        wallet = next(t for t in captured["body"]["tools"] if t["name"] == "get_wallet_info")
        self.assertEqual(wallet["input_schema"], {"type": "object", "properties": {}})

        class Bad:
            def __init__(self, status, message):
                self.status, self.message = status, message

            async def post(self, *a, **k):
                return FakeResponse(status=self.status, json_data={"error": {"message": self.message}})

        cases = [
            (400, "API key not valid. Please pass a valid API key.", "bad_key"),
            (401, "invalid x-api-key", "bad_key"),
            (404, "models/foo is not found for API version v1beta", "bad_model"),
            (429, "quota exceeded", "rate_limit"),
            (500, "internal error", "provider_error"),
        ]
        for status, message, code in cases:
            with mock.patch("asyncio.sleep", new=mock.AsyncMock()):
                with self.assertRaises(LLMError) as cm:
                    await post_json(Bad(status, message), "u", headers={}, body={}, provider="P", model="m")
            self.assertEqual(cm.exception.code, code, (status, message))


if __name__ == "__main__":
    unittest.main()
