// Pure reducer: folds streamed agent events into a chat turn. No React, easy to test.
import type { AgentEvent, AgentTurn, Source, Turn } from "./types"

export function newAgentTurn(id: string): AgentTurn {
  return { id, role: "agent", status: "running", statusText: "Connecting…", notes: [], trace: [], sources: [] }
}

function mergeSources(existing: Source[], incoming: Source[]): Source[] {
  const seen = new Set(existing.map((s) => s.url))
  const out = [...existing]
  for (const s of incoming) {
    if (s.url && !seen.has(s.url)) {
      seen.add(s.url)
      out.push(s)
    }
  }
  return out
}

export function applyEvent(turn: AgentTurn, ev: AgentEvent): AgentTurn {
  switch (ev.type) {
    case "run_started":
      return { ...turn, model: ev.label || ev.model, statusText: "Starting…" }
    case "status":
      return { ...turn, statusText: ev.message }
    case "note":
      return { ...turn, notes: [...turn.notes, ev.text] }
    case "tool_call":
      if (turn.trace.some((t) => t.id === ev.id)) return turn
      return {
        ...turn,
        statusText: `Running ${ev.name}…`,
        trace: [...turn.trace, { id: ev.id, name: ev.name, args: ev.args, status: "running" }],
      }
    case "tool_result":
      return {
        ...turn,
        statusText: "Reading what the tools found…",
        trace: turn.trace.map((t) =>
          t.id === ev.id
            ? {
                ...t,
                status: ev.ok ? "ok" : "error",
                summary: ev.summary,
                output: ev.output,
                durationMs: ev.duration_ms,
                cached: ev.cached,
              }
            : t,
        ),
        sources: mergeSources(turn.sources, ev.sources ?? []),
      }
    case "final":
      return {
        ...turn,
        status: "done",
        statusText: "Done",
        text: ev.text,
        confidence: ev.confidence,
        premiumGap: ev.premium_gap,
        sources: mergeSources([], ev.sources ?? []),
        stats: ev.stats,
      }
    case "error":
      return { ...turn, status: "error", statusText: "Error", error: ev.message }
    case "done":
      return turn.status === "running"
        ? { ...turn, status: "error", statusText: "Error", error: turn.error ?? "The run ended unexpectedly. Please try again." }
        : turn
    default:
      return turn
  }
}

/** Plain text history sent to the API: user questions and finished agent answers only. */
export function buildHistory(turns: Turn[], maxMessages = 12): { role: "user" | "assistant"; content: string }[] {
  const msgs: { role: "user" | "assistant"; content: string }[] = []
  for (const t of turns) {
    if (t.role === "user") msgs.push({ role: "user", content: t.text })
    else if (t.status === "done" && t.text) msgs.push({ role: "assistant", content: t.text })
  }
  let tail = msgs.slice(-maxMessages)
  while (tail.length && tail[0].role !== "user") tail = tail.slice(1)
  return tail
}
