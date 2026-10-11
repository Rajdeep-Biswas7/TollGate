<p align="center">
  <img src="./assets/logo.png" alt="Tollgate logo" width="120" />
</p>

<h1 align="center">TOLLGATE</h1>
<p align="center"><b>A research agent with a wallet.</b><br/>Free sources first. Every tool call visible. Paid x402 data coming next.</p>

---

## Demo

| Week | Build | Demo video |
|------|-------|-----------|
| Week 1 | `tollgate.v1` | **Week 1 (tollgate.v1): `PASTE_DEMO_VIDEO_LINK_HERE`** |
| Week 2 | `tollgate.v2` | Week 2 (tollgate.v2): _coming soon_ |
| Week 3 | `tollgate.v3` | Week 3 (tollgate.v3): _coming soon_ |

## The problem

AI research assistants have two failure modes:

1. **They can't reach the best data.** Premium data (market feeds, research archives, news archives) sits behind subscriptions and API keys. An agent can't just "buy" a single answer, so it settles for whatever is free.
2. **If you let them spend, they overspend.** An agent with a card can burn money on weak sources and nobody can see why.

**Tollgate is a research agent that treats money as a first-class tool.** It always tries free sources first, shows every step it takes, and has its own wallet. In later versions it will pay for premium data over **x402** (HTTP 402 payments) only when free sources are not enough, within limits you set, and show a receipt for every cent.

Who it is for: students, analysts, journalists and builders who want sourced answers and full control over what an agent is allowed to spend.

**Why it matters for the future:** as agents start buying data and services from each other, they need a safe way to pay. Tollgate explores that pattern: metered, itemised, human-capped spending.

> **Week 1 scope:** the free-source research agent, the full-stack app, the live tool trace, model switching, and a testnet wallet. Paid x402 sources are the Week 2 and 3 work (see [Future scope](#future-scope)).

## Key features

- **Nine built-in tools** the agent chooses between on its own (see below).
- **Live tool trace.** Every call streams into the UI; click a step to inspect exactly what was sent and what came back.
- **Model switcher.** Gemini (free tier) and Claude, switchable per question.
- **Honest answers.** Inline source links, a confidence label, and a "paid-source signal" when a premium source would materially improve the answer. This is the hook for the Week 2 buy/skip logic.
- **Agent wallet.** Create a Base Sepolia testnet wallet in one click, see ETH and USDC balances, faucet and BaseScan links. The private key never leaves the backend.
- **Spend meter.** Every run reports `paid_calls` and `cost_usdc` (always `0` in v1, free sources only).
- **Safe by design.** SSRF-guarded page fetching, sandboxed calculator (no `eval`), input validation, rate limiting, untrusted-content prompt rule, per-tool timeouts, a step cap and duplicate-call caching.
- **Three clean services**: `frontend/` (Next.js), `backend/` (Node.js), `ai/` (Python).

## Tools

| # | Tool | What it does | Source |
|---|------|--------------|--------|
| 1 | `web_search` | Current web results with snippets | Tavily (if key set) or DuckDuckGo |
| 2 | `wikipedia_lookup` | Background knowledge, intro summaries | Wikipedia API |
| 3 | `search_papers` | Research papers with abstracts | arXiv API |
| 4 | `fetch_webpage` | Reads a public page as clean text (blocks private IPs, PDFs unsupported) | Any public URL |
| 5 | `hacker_news_search` | Tech, startup and crypto stories | HN Algolia API |
| 6 | `crypto_price` | Live prices, 24h change, market cap | CoinGecko API |
| 7 | `calculator` | Exact arithmetic via a safe AST evaluator | Local |
| 8 | `get_current_time` | Date and time in any timezone | Local |
| 9 | `get_wallet_info` | The agent's address and Base Sepolia balances | Backend wallet service |

## Supported AI models

Switch models in the console dropdown. A model is selectable when its provider key is set in `ai/.env`.

| Model ID | Provider | Notes |
|----------|----------|-------|
| `gemini-flash-latest` | Google Gemini | Default. Free tier. Alias that tracks the latest Flash model |
| `gemini-2.5-flash` | Google Gemini | Pinned Gemini 2.5 Flash |
| `claude-haiku-4-5-20251001` | Anthropic | Claude Haiku 4.5, fast and cheap |
| `claude-sonnet-5-5` | Anthropic | Claude Sonnet 5.5, stronger reasoning |

Edit `ai/app/models.py` to add more. Any id starting with `gemini` or `claude` also works if passed explicitly.

## Tech stack

| Layer | Technology | Version (as declared) |
|-------|-----------|------------------------|
| Frontend | Next.js (App Router) | 16.1.0-canary.0 |
| | React | 19.2.0 |
| | Tailwind CSS | ^4.1.9 |
| | TypeScript | ^5 |
| | GSAP / Lenis / Framer Motion | 3.14.1 / 1.3.15 / 12.23.26 |
| Backend | Node.js (built-in `http`, `fetch`, SSE) | >= 20 |
| | viem (wallet + Base Sepolia RPC) | ^2.21.0 |
| AI service | Python | >= 3.10 (3.11+ recommended) |
| | FastAPI / Uvicorn | >= 0.115 / >= 0.30 |
| | Pydantic | >= 2.7 |
| | httpx | >= 0.27 |
| Network | Base Sepolia testnet (chain id 84532), USDC `0x036CbD53842c5426634e7929541eC2318f3dCF7e` | n/a |

## Architecture

```
 Browser (Next.js, :3000)
    │  POST /api/chat  (SSE stream)     GET/POST /api/wallet
    ▼
 Backend (Node.js, :4000) ───────────────┐
    │  validation · rate limit · run log │ viem
    │  proxies the SSE stream            ▼
    ▼                               Base Sepolia RPC
 AI service (Python/FastAPI, :8000)
    │  agent loop: LLM ⇄ tools (parallel, cached, timed out)
    ├─ Gemini / Claude (REST, function calling)
    └─ Tools → web, Wikipedia, arXiv, HN, CoinGecko, wallet (via backend)
```

The agent loop (`ai/app/agent.py`) sends the conversation and tool schemas to the model, runs the tool calls it requests in parallel, feeds results back, and repeats (max 8 steps) until the model answers. Each step is emitted as an SSE event (`tool_call`, `tool_result`, `final`, ...), which the backend relays to the browser untouched.

## Run it locally

You need **Node.js 20+**, **Python 3.10+**, and a free **Gemini API key** from <https://aistudio.google.com/apikey>.

**1. AI service** (terminal 1)

```bash
cd ai
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then put your GEMINI_API_KEY in ai/.env
uvicorn app.main:app --port 8000
```

**2. Backend** (terminal 2)

```bash
cd backend
npm install
cp .env.example .env               # defaults are fine
npm start
```

**3. Frontend** (terminal 3)

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open <http://localhost:3000>. The status lights in the console should all be on. Click **Create wallet**, then try the suggested prompts.

Optional: add `TAVILY_API_KEY` to `ai/.env` for more reliable web search (free tier at tavily.com), and `ANTHROPIC_API_KEY` to enable the Claude models.

### Tests

```bash
cd ai && python -m unittest discover -s tests -t .     # tools, agent loop, provider formats
cd backend && npm test                                  # API, SSE proxy, validation, rate limit
cd frontend && npm test                                 # event reducer + markdown parser (Node 22+)
```

## Add your own tool

Create `ai/app/tools/my_tool.py`:

```python
from pydantic import BaseModel, Field
from .base import Tool, ToolOutput

class Args(BaseModel):
    city: str = Field(min_length=2, description="City name")

async def run(args: Args) -> ToolOutput:
    return ToolOutput(data={"city": args.city}, summary=f"looked up {args.city}")

TOOL = Tool(name="my_tool", description="When the model should use this tool.", args_model=Args, handler=run)
```

Then add it to `ALL_TOOLS` in `ai/app/tools/__init__.py`. The schema, validation, timeout, UI trace and model wiring are automatic.

## API

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Backend | `POST /api/chat` | `{messages, model?}` → SSE stream of agent events |
| Backend | `GET /api/health` `GET /api/models` `GET /api/runs` | Status, available models, recent runs |
| Backend | `GET/POST /api/wallet` | Wallet info / create (idempotent) |
| AI | `POST /run` `GET /health` `GET /models` `GET /tools` | Agent run (SSE), status, models, tool schemas |

## Security notes

- Testnet only. Never put a real-funds key in `WALLET_PRIVATE_KEY`.
- The wallet file `backend/.agent-wallet.json` and all `.env` files are git-ignored. Never commit them.
- `fetch_webpage` refuses non-http(s) URLs and any host resolving to a private, loopback or link-local address, and re-checks every redirect.
- Text returned by tools is treated as untrusted data in the system prompt.

## Future scope

**Week 2 (`tollgate.v2`)**
- Premium provider registry (your own demo x402 endpoints plus an open plug-in format)
- "Should I pay?" brain: free-first, preview and relevance scoring, cost estimate, buy / skip / ask
- Per-question and daily budgets, approval dialog, post-purchase quality check and provider reputation

**Week 3 (`tollgate.v3`)**
- Real **x402** payments in USDC on Base Sepolia, signed by the backend wallet under spending limits
- On-chain receipts with BaseScan links for every purchase, live spend meter
- Optional privacy mode (hashed research history)

**Later**
- Multi-agent marketplace: agents selling services to other agents over x402
- Streaming tokens, PDF reading, saved research sessions

## Social

- Twitter/X: `PASTE_YOUR_X_PAGE_LINK_HERE`
- Edit `frontend/lib/site.ts` to set the links shown on the site

## License

MIT
