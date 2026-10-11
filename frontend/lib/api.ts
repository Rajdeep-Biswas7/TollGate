import type { AgentEvent, Health, ModelInfo, RunSummary, WalletInfo } from "./types"

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000").replace(/\/+$/, "")

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.error || `Request failed (${res.status})`)
  return body as T
}

export const getHealth = () => getJson<Health>("/api/health")
export const getModels = () => getJson<{ models: ModelInfo[] }>("/api/models").then((r) => r.models)
export const getWallet = () => getJson<WalletInfo>("/api/wallet")
export const createWallet = () => getJson<WalletInfo>("/api/wallet", { method: "POST" })
export const getRuns = () => getJson<{ runs: RunSummary[] }>("/api/runs").then((r) => r.runs)

export type ChatBody = { messages: { role: "user" | "assistant"; content: string }[]; model?: string | null }

/** POST /api/chat and yield Server-Sent Events as they arrive. */
export async function* streamChat(body: ChatBody, signal: AbortSignal): AsyncGenerator<AgentEvent> {
  let res: Response
  try {
    res = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err
    yield {
      type: "error",
      code: "backend_offline",
      message: `Cannot reach the backend at ${API_URL}. Start it with: cd backend && npm start`,
    }
    return
  }

  if (!res.ok || !res.body) {
    const j = await res.json().catch(() => ({}))
    yield { type: "error", code: "http", message: j?.error || `Request failed (${res.status}).` }
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const data = frame
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n")
      if (!data) continue
      try {
        yield JSON.parse(data) as AgentEvent
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
