"""crypto_price: live prices and 24h change from CoinGecko's free API."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..errors import ToolError
from ..net import client
from .base import Source, Tool, ToolOutput

API = "https://api.coingecko.com/api/v3"


class CryptoArgs(BaseModel):
    coins: list[str] = Field(
        min_length=1, max_length=5, description="Coin names or tickers, e.g. ['bitcoin', 'ETH', 'solana']."
    )
    currency: str = Field(default="usd", min_length=3, max_length=5, description="Quote currency, e.g. usd, inr, eur.")


async def _resolve(name: str) -> dict | None:
    r = await client().get(f"{API}/search", params={"query": name})
    if r.status_code == 429:
        raise ToolError("CoinGecko rate limit reached. Wait a minute and try again.")
    r.raise_for_status()
    coins = r.json().get("coins") or []
    if not coins:
        return None
    needle = name.strip().lower()
    for c in coins:
        if needle in (str(c.get("id", "")).lower(), str(c.get("symbol", "")).lower(), str(c.get("name", "")).lower()):
            return c
    return coins[0]


async def run(args: CryptoArgs) -> ToolOutput:
    cur = args.currency.lower().strip()
    resolved: list[dict] = []
    for name in args.coins:
        hit = await _resolve(name)
        if hit and all(hit["id"] != x["id"] for x in resolved):
            resolved.append(hit)
    if not resolved:
        raise ToolError("Could not find any of those coins on CoinGecko.")
    r = await client().get(
        f"{API}/simple/price",
        params={
            "ids": ",".join(c["id"] for c in resolved),
            "vs_currencies": cur,
            "include_market_cap": "true",
            "include_24hr_change": "true",
        },
    )
    if r.status_code == 429:
        raise ToolError("CoinGecko rate limit reached. Wait a minute and try again.")
    r.raise_for_status()
    prices = r.json()
    rows = []
    for c in resolved:
        p = prices.get(c["id"]) or {}
        if cur not in p:
            continue
        change = p.get(f"{cur}_24h_change")
        rows.append(
            {
                "name": c.get("name"),
                "symbol": str(c.get("symbol", "")).upper(),
                "price": p[cur],
                "currency": cur.upper(),
                "change_24h_pct": round(change, 2) if isinstance(change, (int, float)) else None,
                "market_cap": p.get(f"{cur}_market_cap"),
            }
        )
    if not rows:
        raise ToolError(f"CoinGecko has no '{cur}' price for those coins. Try usd.")
    return ToolOutput(
        data={"prices": rows, "source": "CoinGecko"},
        summary=", ".join(f"{r['symbol']} {r['price']:,} {r['currency']}" for r in rows),
        sources=[Source(f"{c.get('name')} on CoinGecko", f"https://www.coingecko.com/en/coins/{c['id']}") for c in resolved],
    )


TOOL = Tool(
    name="crypto_price",
    description="Get live cryptocurrency prices, 24h change and market cap (CoinGecko). Not for historical charts.",
    args_model=CryptoArgs,
    handler=run,
)
