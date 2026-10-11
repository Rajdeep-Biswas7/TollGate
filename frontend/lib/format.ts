export const shortAddress = (a?: string) => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : "")

export function formatMs(ms?: number | null) {
  if (ms == null) return ""
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

export function argsPreview(args: Record<string, unknown>) {
  const first = Object.values(args)[0]
  if (first == null) return ""
  const s = typeof first === "string" ? first : JSON.stringify(first)
  return s.length > 70 ? s.slice(0, 67) + "…" : s
}
