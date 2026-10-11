"use client"

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react"
import { ArrowUp, Square, Trash2 } from "lucide-react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { cn } from "@/lib/utils"
import { getHealth, getModels, getRuns, streamChat } from "@/lib/api"
import { applyEvent, buildHistory, newAgentTurn } from "@/lib/agent-state"
import type { AgentTurn, Health, ModelInfo, RunSummary, Turn } from "@/lib/types"
import { AnswerBlock } from "./answer"
import { TraceRow } from "./trace"
import { WalletPanel } from "./wallet-panel"
import { RunLog } from "./run-log"

gsap.registerPlugin(ScrollTrigger)

const SUGGESTIONS = [
  "What is x402 and why does it matter for AI agents?",
  "Price of ETH and BTC right now, and how did they move today?",
  "Summarise recent research on retrieval-augmented generation",
  "How many days from today until 1 January 2027? Use timezone Asia/Kolkata",
  "What is in your wallet?",
]

const uid = () => Math.random().toString(36).slice(2, 10)

function Led({ state, label }: { state: "ok" | "bad" | "unknown"; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          state === "ok" && "bg-accent",
          state === "bad" && "bg-destructive",
          state === "unknown" && "animate-pulse bg-muted-foreground/60",
        )}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

export function AgentConsole() {
  const sectionRef = useRef<HTMLElement>(null)
  const headerRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const stickRef = useRef(true)
  const abortRef = useRef<AbortController | null>(null)
  const turnsRef = useRef<Turn[]>([])

  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState<Health | "offline" | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [model, setModel] = useState<string>("")
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [fresh, setFresh] = useState<Set<string>>(new Set()) // answers that should type out

  turnsRef.current = turns

  // ---- header entrance, same motion language as the other sections
  useEffect(() => {
    if (!sectionRef.current || !headerRef.current) return
    const ctx = gsap.context(() => {
      gsap.fromTo(
        headerRef.current,
        { x: -60, opacity: 0 },
        { x: 0, opacity: 1, duration: 1, ease: "power3.out", scrollTrigger: { trigger: headerRef.current, start: "top 90%", toggleActions: "play none none reverse" } },
      )
    }, sectionRef)
    return () => ctx.revert()
  }, [])

  // ---- health + models polling
  const refreshRuns = useCallback(() => {
    getRuns().then(setRuns).catch(() => {})
  }, [])

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const h = await getHealth()
        if (!alive) return
        setHealth(h)
        if (h.ai.reachable) {
          const m = await getModels().catch(() => [] as ModelInfo[])
          if (!alive) return
          setModels(m)
          setModel((cur) => (cur && m.some((x) => x.id === cur && x.available) ? cur : (m.find((x) => x.available)?.id ?? "")))
        }
      } catch {
        if (alive) setHealth("offline")
      }
    }
    void load()
    refreshRuns()
    const id = window.setInterval(load, 15000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [refreshRuns])

  // ---- keep the chat pinned to the bottom unless the user scrolled up
  useEffect(() => {
    const inner = innerRef.current
    const outer = listRef.current
    if (!inner || !outer) return
    const ro = new ResizeObserver(() => {
      if (stickRef.current) outer.scrollTop = outer.scrollHeight
    })
    ro.observe(inner)
    return () => ro.disconnect()
  }, [])

  const onScroll = () => {
    const el = listRef.current
    if (el) stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  const backendUp = health !== null && health !== "offline"
  const aiUp = backendUp && (health as Health).ai.reachable
  const anyModel = models.some((m) => m.available)

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || busy) return
      stickRef.current = true
      const userTurn: Turn = { id: uid(), role: "user", text }
      const agentTurn = newAgentTurn(uid())
      const history = buildHistory([...turnsRef.current, userTurn])
      setTurns((t) => [...t, userTurn, agentTurn])
      setInput("")
      if (inputRef.current) inputRef.current.style.height = "auto"
      setBusy(true)

      const ac = new AbortController()
      abortRef.current = ac
      const patch = (fn: (t: AgentTurn) => AgentTurn) =>
        setTurns((all) => all.map((t) => (t.id === agentTurn.id && t.role === "agent" ? fn(t) : t)))

      try {
        for await (const ev of streamChat({ messages: history, model: model || null }, ac.signal)) {
          if (ev.type === "final") setFresh((s) => new Set(s).add(agentTurn.id))
          patch((t) => applyEvent(t, ev))
        }
        patch((t) => applyEvent(t, { type: "done" }))
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          patch((t) => ({ ...t, status: "error", statusText: "Stopped", error: "Stopped." }))
        } else {
          patch((t) => ({ ...t, status: "error", statusText: "Error", error: (err as Error).message || "Something went wrong." }))
        }
      } finally {
        abortRef.current = null
        setBusy(false)
        refreshRuns()
        inputRef.current?.focus()
      }
    },
    [busy, model, refreshRuns],
  )

  const stop = () => abortRef.current?.abort()
  const clear = () => {
    abortRef.current?.abort()
    setTurns([])
    setFresh(new Set())
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void send(input)
    }
  }

  const onInput = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    e.target.style.height = "auto"
    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`
  }

  return (
    <section ref={sectionRef} id="console" className="relative py-32 pl-6 md:pl-28 pr-6 md:pr-12">
      <div ref={headerRef} className="mb-12 flex items-end justify-between">
        <div>
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-accent">01 / Console</span>
          <h2 className="mt-4 font-[var(--font-bebas)] text-5xl md:text-7xl tracking-tight">RUN THE AGENT</h2>
        </div>
        <p className="hidden md:block max-w-xs text-right font-mono text-xs leading-relaxed text-muted-foreground">
          Every tool call is visible. Click a step to inspect what was sent and what came back.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* ---------------------------------------------------------------- chat */}
        <div className="flex h-[680px] flex-col border border-border/40 bg-card/40">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/40 px-4 py-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <Led state={health === null ? "unknown" : backendUp ? "ok" : "bad"} label="Backend" />
              <Led state={health === null ? "unknown" : aiUp ? "ok" : "bad"} label="AI" />
              <Led state={!aiUp ? "unknown" : anyModel ? "ok" : "bad"} label="Model key" />
            </div>
            <div className="flex items-center gap-3">
              <label className="sr-only" htmlFor="model-select">
                Model
              </label>
              <select
                id="model-select"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={busy || models.length === 0}
                className="max-w-[12rem] border border-border/50 bg-background px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-foreground outline-none focus:border-accent disabled:opacity-50"
              >
                {models.length === 0 && <option value="">Model</option>}
                {models.map((m) => (
                  <option key={m.id} value={m.id} disabled={!m.available}>
                    {m.label}
                    {m.available ? "" : " (no key)"}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={clear}
                disabled={turns.length === 0}
                className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground disabled:opacity-30"
              >
                <Trash2 className="h-3 w-3" /> Clear
              </button>
            </div>
          </div>

          {(health === "offline" || (backendUp && !aiUp) || (aiUp && !anyModel)) && (
            <div role="alert" className="border-b border-destructive/40 bg-destructive/10 px-4 py-2.5 font-mono text-[11px] leading-relaxed text-foreground/90">
              {health === "offline" && "Backend is offline. Run: cd backend && npm start"}
              {backendUp && !aiUp && "AI service is offline. Run: cd ai && uvicorn app.main:app --port 8000"}
              {aiUp && !anyModel && "No model API key found. Add GEMINI_API_KEY (free) to ai/.env and restart the AI service."}
            </div>
          )}

          <div ref={listRef} onScroll={onScroll} data-lenis-prevent aria-live="polite" className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
            <div ref={innerRef} className="space-y-8">
              {turns.length === 0 && (
                <div className="py-6">
                  <p className="font-[var(--font-bebas)] text-4xl tracking-tight text-foreground/90 md:text-6xl">ASK ANYTHING.</p>
                  <p className="mt-3 max-w-md font-mono text-xs leading-relaxed text-muted-foreground">
                    The agent tries free sources first and shows its work. Pick a prompt or write your own.
                  </p>
                  <ul className="mt-6 flex flex-col items-start gap-2">
                    {SUGGESTIONS.map((s) => (
                      <li key={s}>
                        <button
                          type="button"
                          onClick={() => send(s)}
                          disabled={busy}
                          className="border border-border/40 px-3 py-2 text-left font-mono text-[11px] text-muted-foreground transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
                        >
                          {s}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {turns.map((t) =>
                t.role === "user" ? (
                  <div key={t.id}>
                    <div className="mb-1.5 font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">You</div>
                    <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed">{t.text}</p>
                  </div>
                ) : (
                  <div key={t.id} className="space-y-3">
                    <div className="flex items-center gap-3 font-mono text-[9px] uppercase tracking-[0.3em] text-accent">
                      <span>Agent</span>
                      {t.status === "running" && <span className="animate-pulse text-muted-foreground">{t.statusText}</span>}
                    </div>

                    {t.notes.map((n, i) => (
                      <p key={i} className="border-l border-accent/40 pl-3 font-mono text-[11px] italic leading-relaxed text-muted-foreground">
                        {n}
                      </p>
                    ))}

                    {t.trace.length > 0 && (
                      <div className="space-y-1.5">
                        {t.trace.map((item) => (
                          <TraceRow key={item.id} item={item} />
                        ))}
                      </div>
                    )}

                    {t.status === "done" && t.text && <AnswerBlock turn={t} animate={fresh.has(t.id)} />}

                    {t.status === "error" && (
                      <p role="alert" className="border border-destructive/50 bg-destructive/10 px-3 py-2 font-mono text-[11px] leading-relaxed">
                        {t.error}
                      </p>
                    )}
                  </div>
                ),
              )}
            </div>
          </div>

          <div className="border-t border-border/40 p-3 md:p-4">
            <div className="flex items-end gap-3">
              <label htmlFor="agent-input" className="sr-only">
                Ask the agent
              </label>
              <textarea
                id="agent-input"
                ref={inputRef}
                data-lenis-prevent
                rows={1}
                value={input}
                onChange={onInput}
                onKeyDown={onKeyDown}
                maxLength={4000}
                placeholder="Ask a research question…"
                className="max-h-[140px] min-h-[44px] flex-1 resize-none border border-border/50 bg-background px-3 py-2.5 font-mono text-[13px] leading-relaxed outline-none placeholder:text-muted-foreground/60 focus:border-accent"
              />
              {busy ? (
                <button type="button" onClick={stop} aria-label="Stop" className="flex h-11 w-11 shrink-0 items-center justify-center border border-destructive/60 text-destructive transition-colors hover:bg-destructive/10">
                  <Square className="h-4 w-4 fill-current" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => send(input)}
                  disabled={!input.trim() || !aiUp || !anyModel}
                  aria-label="Send"
                  className="flex h-11 w-11 shrink-0 items-center justify-center border border-foreground/20 transition-all hover:border-accent hover:text-accent disabled:opacity-30 disabled:hover:border-foreground/20 disabled:hover:text-foreground"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
              )}
            </div>
            <p className="mt-2 font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">Enter to send · Shift+Enter for a new line</p>
          </div>
        </div>

        {/* ------------------------------------------------------------- sidebar */}
        <aside className="space-y-6">
          <WalletPanel backendUp={backendUp} />

          <div className="border border-border/40 bg-card/40 p-5">
            <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.3em] text-accent">Spend meter</div>
            <div className="font-[var(--font-bebas)] text-4xl leading-none">$0.000</div>
            <div className="mt-3 h-1 w-full bg-secondary">
              <div className="h-full w-0 bg-accent" />
            </div>
            <p className="mt-3 font-mono text-[10px] leading-relaxed text-muted-foreground">
              Spend is tracked per answer. Right now every answer uses free sources only. Paid x402 sources and spending limits are coming next.
            </p>
          </div>

          <RunLog runs={runs} />
        </aside>
      </div>
    </section>
  )
}
