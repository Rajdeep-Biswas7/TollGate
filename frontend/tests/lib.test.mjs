// Run with: node --test tests/   (Node 22+ strips TypeScript types automatically)
import { test } from "node:test"
import assert from "node:assert/strict"
import { applyEvent, newAgentTurn, buildHistory } from "../lib/agent-state.ts"
import { parseBlocks, parseInline } from "../lib/markdown.ts"

test("reducer folds a full run", () => {
  let t = newAgentTurn("a1")
  const events = [
    { type: "run_started", run_id: "r", model: "m", provider: "gemini", label: "Gemini Flash" },
    { type: "status", message: "Thinking…" },
    { type: "tool_call", id: "1:x", name: "web_search", args: { query: "hi" }, step: 1 },
    { type: "tool_call", id: "1:x", name: "web_search", args: { query: "hi" }, step: 1 }, // duplicate ignored
    { type: "tool_result", id: "1:x", name: "web_search", ok: true, summary: "5 results", output: "{}", duration_ms: 900, cached: false, sources: [{ title: "A", url: "https://a.com" }] },
    { type: "final", text: "Answer", confidence: "high", premium_gap: null, sources: [{ title: "A", url: "https://a.com" }, { title: "A2", url: "https://a.com" }], stats: { steps: 2, tool_calls: 1, tools_used: ["web_search"], duration_ms: 1500, input_tokens: 1, output_tokens: 1, paid_calls: 0, cost_usdc: 0 } },
    { type: "done" },
  ]
  for (const e of events) t = applyEvent(t, e)
  assert.equal(t.status, "done")
  assert.equal(t.model, "Gemini Flash")
  assert.equal(t.trace.length, 1)
  assert.equal(t.trace[0].status, "ok")
  assert.equal(t.sources.length, 1)
  assert.equal(t.text, "Answer")
})

test("reducer: error and unexpected end", () => {
  let t = applyEvent(newAgentTurn("a"), { type: "error", code: "x", message: "boom" })
  t = applyEvent(t, { type: "done" })
  assert.equal(t.status, "error")
  assert.equal(t.error, "boom")
  const u = applyEvent(newAgentTurn("b"), { type: "done" })
  assert.equal(u.status, "error")
})

test("history keeps finished answers only and starts with a user message", () => {
  const turns = [
    { id: "1", role: "user", text: "q1" },
    { ...newAgentTurn("a1"), status: "done", text: "a1" },
    { id: "2", role: "user", text: "q2" },
    { ...newAgentTurn("a2"), status: "error", error: "x" },
    { id: "3", role: "user", text: "q3" },
  ]
  assert.deepEqual(buildHistory(turns).map((m) => m.content), ["q1", "a1", "q2", "q3"])
  assert.deepEqual(buildHistory(turns, 3).map((m) => m.content), ["q2", "q3"].slice(0, 2)) // trimmed tail starts on a user turn
})

test("markdown inline: bold, code, links, bare urls, no javascript: links", () => {
  const out = parseInline("**Hi** `x` [Doc](https://a.com/p?q=1) and https://b.org/x. [bad](javascript:alert(1))")
  assert.deepEqual(out.filter((i) => i.t !== "text").map((i) => i.t), ["bold", "code", "link", "link"])
  assert.equal(out.find((i) => i.t === "link" && i.v === "https://b.org/x").href, "https://b.org/x")
  assert.ok(!out.some((i) => i.t === "link" && i.href.startsWith("javascript")))
})

test("markdown blocks", () => {
  const b = parseBlocks("# Title\n\nSome text\nmore text\n\n- a\n- b\n\n1. one\n2. two\n\n```\ncode\n```\n\n| a | b |\n|---|---|")
  assert.deepEqual(b.map((x) => x.t), ["h", "p", "ul", "ol", "code", "pre"])
  assert.equal(b[2].items.length, 2)
  assert.equal(b[1].inline[0].v, "Some text more text")
})
