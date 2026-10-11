"use client"

import { useCallback, useEffect, useState } from "react"
import { Check, Copy, ExternalLink, RefreshCw } from "lucide-react"
import { createWallet, getWallet } from "@/lib/api"
import { shortAddress } from "@/lib/format"
import type { WalletInfo } from "@/lib/types"

export function WalletPanel({ backendUp }: { backendUp: boolean }) {
  const [wallet, setWallet] = useState<WalletInfo | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const load = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      setWallet(await getWallet())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    if (backendUp) void load()
  }, [backendUp, load])

  const create = async () => {
    setBusy(true)
    setError(null)
    try {
      setWallet(await createWallet())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const copy = async () => {
    if (!wallet?.address) return
    try {
      await navigator.clipboard.writeText(wallet.address)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <div className="border border-border/40 bg-card/40 p-5">
      <div className="mb-4 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-accent">Agent wallet</span>
        <button
          type="button"
          onClick={load}
          disabled={busy || !backendUp}
          aria-label="Refresh wallet"
          className="text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
        </button>
      </div>

      {!backendUp && <p className="font-mono text-[11px] text-muted-foreground">Backend offline. Start it to use the wallet.</p>}

      {backendUp && wallet && !wallet.exists && (
        <div className="space-y-3">
          <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
            No wallet yet. Create a testnet wallet on Base Sepolia for your agent.
          </p>
          <button
            type="button"
            onClick={create}
            disabled={busy}
            className="w-full border border-foreground/20 px-4 py-2.5 font-mono text-[11px] uppercase tracking-widest transition-all hover:border-accent hover:text-accent disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create wallet"}
          </button>
        </div>
      )}

      {backendUp && wallet?.exists && (
        <div className="space-y-4">
          <button
            type="button"
            onClick={copy}
            className="flex w-full items-center justify-between gap-2 border border-border/40 px-3 py-2 font-mono text-[11px] transition-colors hover:border-accent"
            title={wallet.address}
          >
            <span>{shortAddress(wallet.address)}</span>
            {copied ? <Check className="h-3 w-3 text-accent" /> : <Copy className="h-3 w-3 text-muted-foreground" />}
          </button>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">ETH</div>
              <div className="mt-1 font-[var(--font-bebas)] text-3xl leading-none">{wallet.eth ?? "—"}</div>
            </div>
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground">USDC</div>
              <div className="mt-1 font-[var(--font-bebas)] text-3xl leading-none">{wallet.usdc ?? "—"}</div>
            </div>
          </div>
          {wallet.balanceError && <p className="font-mono text-[10px] text-destructive">{wallet.balanceError}</p>}

          <ul className="space-y-1.5 font-mono text-[10px] uppercase tracking-widest">
            {wallet.explorerUrl && (
              <li>
                <a href={wallet.explorerUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-accent">
                  View on BaseScan <ExternalLink className="h-2.5 w-2.5" />
                </a>
              </li>
            )}
            {wallet.faucets?.map((f) => (
              <li key={f.url}>
                <a href={f.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-accent">
                  {f.label} <ExternalLink className="h-2.5 w-2.5" />
                </a>
              </li>
            ))}
          </ul>
          <p className="border-t border-border/30 pt-3 font-mono text-[10px] leading-relaxed text-muted-foreground/80">
            {wallet.network} testnet only. The private key stays on the backend and is never sent to the browser.
          </p>
        </div>
      )}

      {error && <p className="mt-3 font-mono text-[11px] text-destructive">{error}</p>}
    </div>
  )
}
