export type Source = { title: string; url: string; tool?: string }

export type Stats = {
  steps: number
  tool_calls: number
  tools_used: string[]
  duration_ms: number
  input_tokens: number
  output_tokens: number
  paid_calls: number
  cost_usdc: number
}

export type Confidence = "high" | "medium" | "low"

export type AgentEvent =
  | { type: "run_started"; run_id: string; model: string; provider: string; label: string }
  | { type: "status"; message: string }
  | { type: "note"; text: string }
  | { type: "tool_call"; id: string; name: string; args: Record<string, unknown>; step: number }
  | {
      type: "tool_result"
      id: string
      name: string
      ok: boolean
      summary: string
      output: string
      duration_ms: number
      cached: boolean
      sources: Source[]
    }
  | {
      type: "final"
      text: string
      confidence: Confidence | null
      premium_gap: string | null
      sources: Source[]
      stats: Stats
    }
  | { type: "error"; code: string; message: string }
  | { type: "done" }

export type TraceItem = {
  id: string
  name: string
  args: Record<string, unknown>
  status: "running" | "ok" | "error"
  summary?: string
  output?: string
  durationMs?: number
  cached?: boolean
}

export type UserTurn = { id: string; role: "user"; text: string }

export type AgentTurn = {
  id: string
  role: "agent"
  status: "running" | "done" | "error"
  statusText: string
  model?: string
  notes: string[]
  trace: TraceItem[]
  text?: string
  confidence?: Confidence | null
  premiumGap?: string | null
  sources: Source[]
  stats?: Stats
  error?: string
}

export type Turn = UserTurn | AgentTurn

export type ModelInfo = { id: string; provider: string; label: string; note: string; available: boolean }

export type Health = {
  status: string
  backend: { ok: boolean }
  ai: { reachable: boolean; models_available?: string[]; search_provider?: string; tool_count?: number }
  wallet: { exists: boolean }
}

export type WalletInfo = {
  exists: boolean
  address?: string
  network: string
  chainId: number
  eth?: string | null
  usdc?: string | null
  explorerUrl?: string
  faucets?: { label: string; url: string }[]
  balanceError?: string
}

export type RunSummary = {
  id: string
  question: string
  model: string
  tools: string[]
  status: "running" | "ok" | "error" | "cancelled"
  durationMs: number | null
  startedAt: string
}
