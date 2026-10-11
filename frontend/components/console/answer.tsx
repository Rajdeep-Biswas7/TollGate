"use client"

import { useEffect, useState } from "react"
import { ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatMs } from "@/lib/format"
import type { AgentTurn } from "@/lib/types"
import { Markdown } from "./markdown"

const CONFIDENCE_STYLE = {
  high: "border-accent text-accent",
  medium: "border-foreground/40 text-foreground/80",
  low: "border-destructive text-destructive",
} as const

export function AnswerBlock({ turn, animate }: { turn: AgentTurn; animate: boolean }) {
  const text = turn.text ?? ""
  const [shown, setShown] = useState(animate ? 0 : text.length)

  useEffect(() => {
    if (!animate) {
      setShown(text.length)
      return
    }
    let n = 0
    const step = Math.max(3, Math.ceil(text.length / 90))
    const id = window.setInterval(() => {
      n = Math.min(text.length, n + step)
      setShown(n)
      if (n >= text.length) window.clearInterval(id)
    }, 16)
    return () => window.clearInterval(id)
  }, [text, animate])

  const done = shown >= text.length
  const stats = turn.stats

  return (
    <div className="space-y-4">
      <div onClick={() => setShown(text.length)} className="cursor-text">
        <Markdown text={text.slice(0, shown)} />
        {!done && <span className="ml-0.5 inline-block h-4 w-2 translate-y-0.5 animate-pulse bg-accent" aria-hidden="true" />}
      </div>

      {done && (
        <>
          {turn.premiumGap && (
            <div className="border border-dashed border-accent/40 bg-accent/5 p-3">
              <div className="font-mono text-[9px] uppercase tracking-[0.3em] text-accent">Paid-source signal</div>
              <p className="mt-1 font-mono text-[11px] leading-relaxed text-muted-foreground">
                A premium source could improve this answer: {turn.premiumGap}
              </p>
            </div>
          )}

          {turn.sources.length > 0 && (
            <div>
              <div className="mb-2 font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">
                Sources consulted · {turn.sources.length}
              </div>
              <ul className="flex flex-wrap gap-2">
                {turn.sources.slice(0, 12).map((s, i) => (
                  <li key={s.url}>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={s.url}
                      className="group inline-flex max-w-[16rem] items-center gap-2 border border-border/40 px-2.5 py-1 font-mono text-[10px] text-muted-foreground transition-colors hover:border-accent hover:text-accent"
                    >
                      <span className="text-accent/70">{String(i + 1).padStart(2, "0")}</span>
                      <span className="truncate">{s.title || s.url}</span>
                      <ExternalLink className="h-2.5 w-2.5 shrink-0 opacity-50 group-hover:opacity-100" />
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border/30 pt-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {turn.confidence && (
              <span className={cn("border px-2 py-0.5", CONFIDENCE_STYLE[turn.confidence])}>Confidence · {turn.confidence}</span>
            )}
            {stats && (
              <>
                <span>{stats.tool_calls} tool calls</span>
                <span>{formatMs(stats.duration_ms)}</span>
                <span className="text-accent">spent ${stats.cost_usdc.toFixed(3)} · free sources only</span>
                {turn.model && <span>{turn.model}</span>}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
