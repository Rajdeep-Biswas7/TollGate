import type { ReactNode } from "react"
import { parseBlocks, parseInline, type Inline } from "@/lib/markdown"

function renderInline(items: Inline[]): ReactNode[] {
  return items.map((it, i) => {
    switch (it.t) {
      case "bold":
        return (
          <strong key={i} className="font-semibold text-foreground">
            {it.v}
          </strong>
        )
      case "code":
        return (
          <code key={i} className="bg-secondary px-1.5 py-0.5 font-mono text-[12px] text-accent">
            {it.v}
          </code>
        )
      case "link":
        return (
          <a
            key={i}
            href={it.href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-accent/40 underline-offset-4 hover:decoration-accent break-words"
          >
            {it.v}
          </a>
        )
      default:
        return <span key={i}>{it.v}</span>
    }
  })
}

export function Markdown({ text }: { text: string }) {
  const blocks = parseBlocks(text)
  return (
    <div className="space-y-3 text-[14px] leading-relaxed text-foreground/90">
      {blocks.map((b, i) => {
        switch (b.t) {
          case "h":
            return (
              <h4 key={i} className="pt-2 font-mono text-[11px] uppercase tracking-[0.25em] text-accent">
                {renderInline(b.inline)}
              </h4>
            )
          case "ul":
            return (
              <ul key={i} className="space-y-1.5">
                {b.items.map((it, j) => (
                  <li key={j} className="flex gap-3">
                    <span className="mt-[0.7em] h-1 w-1 shrink-0 bg-accent" aria-hidden="true" />
                    <span>{renderInline(it)}</span>
                  </li>
                ))}
              </ul>
            )
          case "ol":
            return (
              <ol key={i} className="space-y-1.5">
                {b.items.map((it, j) => (
                  <li key={j} className="flex gap-3">
                    <span className="shrink-0 font-mono text-[11px] leading-[1.9] text-accent">{String(j + 1).padStart(2, "0")}</span>
                    <span>{renderInline(it)}</span>
                  </li>
                ))}
              </ol>
            )
          case "code":
          case "pre":
            return (
              <pre
                key={i}
                data-lenis-prevent
                className="max-h-64 overflow-auto border border-border/40 bg-background/60 p-3 font-mono text-[12px] leading-relaxed"
              >
                {b.v}
              </pre>
            )
          default:
            return <p key={i}>{renderInline(b.inline)}</p>
        }
      })}
    </div>
  )
}

export { parseInline }
