// Tiny, safe Markdown subset (no HTML injection): paragraphs, headings, lists, code, bold, links.
export type Inline =
  | { t: "text"; v: string }
  | { t: "bold"; v: string }
  | { t: "code"; v: string }
  | { t: "link"; v: string; href: string }

export type Block =
  | { t: "p"; inline: Inline[] }
  | { t: "h"; level: number; inline: Inline[] }
  | { t: "ul"; items: Inline[][] }
  | { t: "ol"; items: Inline[][] }
  | { t: "code"; v: string }
  | { t: "pre"; v: string }

const TOKEN = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\)|https?:\/\/[^\s<>()]+)/g

export function parseInline(text: string): Inline[] {
  const out: Inline[] = []
  let last = 0
  for (const m of text.matchAll(TOKEN)) {
    const i = m.index ?? 0
    if (i > last) out.push({ t: "text", v: text.slice(last, i) })
    const tok = m[0]
    if (tok.startsWith("**")) out.push({ t: "bold", v: tok.slice(2, -2) })
    else if (tok.startsWith("`")) out.push({ t: "code", v: tok.slice(1, -1) })
    else if (tok.startsWith("[")) {
      const close = tok.indexOf("](")
      out.push({ t: "link", v: tok.slice(1, close), href: tok.slice(close + 2, -1) })
    } else {
      const trimmed = tok.replace(/[.,;:!?]+$/, "")
      out.push({ t: "link", v: trimmed, href: trimmed })
      if (trimmed.length < tok.length) out.push({ t: "text", v: tok.slice(trimmed.length) })
    }
    last = i + tok.length
  }
  if (last < text.length) out.push({ t: "text", v: text.slice(last) })
  return out
}

export function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n")
  const blocks: Block[] = []
  let para: string[] = []
  let list: { kind: "ul" | "ol"; items: Inline[][] } | null = null
  let fence: string[] | null = null
  let table: string[] = []

  const flushPara = () => {
    if (para.length) blocks.push({ t: "p", inline: parseInline(para.join(" ")) })
    para = []
  }
  const flushList = () => {
    if (list) blocks.push({ t: list.kind, items: list.items })
    list = null
  }
  const flushTable = () => {
    if (table.length) blocks.push({ t: "pre", v: table.join("\n") })
    table = []
  }
  const flushAll = () => {
    flushPara()
    flushList()
    flushTable()
  }

  for (const line of lines) {
    if (fence) {
      if (line.trim().startsWith("```")) {
        blocks.push({ t: "code", v: fence.join("\n") })
        fence = null
      } else fence.push(line)
      continue
    }
    if (line.trim().startsWith("```")) {
      flushAll()
      fence = []
      continue
    }
    const trimmed = line.trim()
    if (!trimmed) {
      flushAll()
      continue
    }
    if (trimmed.startsWith("|")) {
      flushPara()
      flushList()
      table.push(trimmed)
      continue
    }
    flushTable()
    const h = /^(#{1,4})\s+(.*)$/.exec(trimmed)
    if (h) {
      flushPara()
      flushList()
      blocks.push({ t: "h", level: h[1].length, inline: parseInline(h[2]) })
      continue
    }
    const ul = /^[-*•]\s+(.*)$/.exec(trimmed)
    const ol = /^\d+[.)]\s+(.*)$/.exec(trimmed)
    if (ul || ol) {
      flushPara()
      const kind = ul ? "ul" : "ol"
      if (list && list.kind !== kind) flushList()
      if (!list) list = { kind, items: [] }
      list.items.push(parseInline((ul ?? ol)![1]))
      continue
    }
    flushList()
    para.push(trimmed)
  }
  if (fence) blocks.push({ t: "code", v: fence.join("\n") })
  flushAll()
  return blocks
}
