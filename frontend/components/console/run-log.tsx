"use client"

import { cn } from "@/lib/utils"
import { formatMs } from "@/lib/format"
import type { RunSummary } from "@/lib/types"

export function RunLog({ runs }: { runs: RunSummary[] }) {
  return (
    <div className="border border-border/40 bg-card/40 p-5">
      <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.3em] text-accent">Run log</div>
      {runs.length === 0 ? (
        <p className="font-mono text-[11px] text-muted-foreground">Nothing yet. Ask the agent something.</p>
      ) : (
        <ul className="space-y-3">
          {runs.slice(0, 5).map((r) => (
            <li key={r.id} className="border-l border-border/50 pl-3">
              <p className="truncate font-mono text-[11px] text-foreground/90" title={r.question}>
                {r.question}
              </p>
              <p className="mt-0.5 flex flex-wrap gap-x-2 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                <span className={cn(r.status === "ok" && "text-accent", r.status === "error" && "text-destructive")}>{r.status}</span>
                <span>{formatMs(r.durationMs)}</span>
                <span>{r.tools.length} tools</span>
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
