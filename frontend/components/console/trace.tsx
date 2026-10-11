"use client"

import { useState } from "react"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { argsPreview, formatMs } from "@/lib/format"
import type { TraceItem } from "@/lib/types"

export function TraceRow({ item }: { item: TraceItem }) {
  const [open, setOpen] = useState(false)
  const running = item.status === "running"
  return (
    <div className="border border-border/30 bg-background/40">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-3 py-2 text-left font-mono text-[11px] hover:bg-accent/5"
      >
        <ChevronRight className={cn("h-3 w-3 shrink-0 text-muted-foreground transition-transform", open && "rotate-90")} />
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full",
            running && "animate-pulse bg-accent",
            item.status === "ok" && "bg-accent",
            item.status === "error" && "bg-destructive",
          )}
          aria-hidden="true"
        />
        <span className="shrink-0 uppercase tracking-widest text-foreground">{item.name}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">{argsPreview(item.args)}</span>
        <span className="shrink-0 text-muted-foreground/70">
          {running ? "running…" : `${item.cached ? "cached · " : ""}${formatMs(item.durationMs)}`}
        </span>
      </button>

      {item.summary && !open && (
        <p className={cn("px-3 pb-2 pl-[2.6rem] font-mono text-[10px]", item.status === "error" ? "text-destructive" : "text-muted-foreground")}>
          {item.summary}
        </p>
      )}

      {open && (
        <div className="space-y-3 border-t border-border/30 p-3">
          <div>
            <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">Sent</div>
            <pre data-lenis-prevent className="max-h-40 overflow-auto bg-background/60 p-2 font-mono text-[11px] leading-relaxed">
              {JSON.stringify(item.args, null, 2)}
            </pre>
          </div>
          <div>
            <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">Received</div>
            <pre data-lenis-prevent className="max-h-56 overflow-auto bg-background/60 p-2 font-mono text-[11px] leading-relaxed">
              {item.output ?? "waiting…"}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
