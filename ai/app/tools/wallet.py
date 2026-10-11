"""get_wallet_info: the agent's own Base Sepolia wallet (held by the Node backend).

Week 1 only reads the wallet. The private key never leaves the backend; in later weeks the
backend will also sign x402 payments on the agent's behalf, under spending limits.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..config import settings
from ..errors import ToolError
from ..net import client
from .base import Source, Tool, ToolOutput


class NoArgs(BaseModel):
    pass


async def run(_args: NoArgs) -> ToolOutput:
    try:
        r = await client().get(f"{settings.backend_url}/api/wallet", timeout=8.0)
        r.raise_for_status()
    except Exception as exc:
        raise ToolError("Could not reach the wallet service. Is the backend running on " + settings.backend_url + "?") from exc
    w = r.json()
    if not w.get("exists"):
        return ToolOutput(
            data={"exists": False, "hint": "The user has not created a wallet yet. They can click 'Create wallet' in the console."},
            summary="no wallet created yet",
        )
    data = {
        "address": w.get("address"),
        "network": w.get("network"),
        "eth_balance": w.get("eth"),
        "usdc_balance": w.get("usdc"),
        "note": "Testnet funds only, no real value.",
    }
    return ToolOutput(
        data=data,
        summary=f"{str(w.get('address'))[:6]}…{str(w.get('address'))[-4:]} · {w.get('eth')} ETH · {w.get('usdc')} USDC",
        sources=[Source("Wallet on BaseScan", w.get("explorerUrl") or "https://sepolia.basescan.org")],
    )


TOOL = Tool(
    name="get_wallet_info",
    description="Show the agent's own crypto wallet: address and balances on Base Sepolia testnet. Use when asked about the wallet or funds.",
    args_model=NoArgs,
    handler=run,
    category="wallet",
)
