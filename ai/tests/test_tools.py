import unittest
from unittest import mock

from tests import _stubs  # noqa: F401
from tests.fakes import FakeHttp, FakeResponse

from app.errors import ToolError
from app.tools import ALL_TOOLS, execute, get_tool


class RegistryTests(unittest.TestCase):
    def test_at_least_five_unique_tools_with_specs(self):
        self.assertGreaterEqual(len(ALL_TOOLS), 5)
        names = [t.name for t in ALL_TOOLS]
        self.assertEqual(len(names), len(set(names)))
        for t in ALL_TOOLS:
            spec = t.spec()
            self.assertTrue(t.description)
            self.assertEqual(spec.parameters.get("type"), "object")
            self.assertNotIn("title", spec.parameters)


class ExecuteTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_args_become_error_not_exception(self):
        run = await execute(get_tool("calculator"), {})
        self.assertFalse(run.ok)
        self.assertIn("Invalid arguments", run.error)
        run = await execute(get_tool("web_search"), {"query": "x"})  # too short
        self.assertFalse(run.ok)

    async def test_calculator_and_clock(self):
        run = await execute(get_tool("calculator"), {"expression": "15% of 200"})
        self.assertFalse(run.ok)  # unsupported syntax is reported, not crashed
        run = await execute(get_tool("calculator"), {"expression": "0.15 * 200"})
        self.assertTrue(run.ok)
        self.assertEqual(run.output.data["result"], 30)
        run = await execute(get_tool("get_current_time"), {"timezone": "Asia/Kolkata"})
        self.assertTrue(run.ok, run.error)
        self.assertEqual(run.output.data["utc_offset"], "+0530")
        run = await execute(get_tool("get_current_time"), {"timezone": "Mars/Base"})
        self.assertFalse(run.ok)

    async def test_wikipedia(self):
        payload = {"query": {"pages": {
            "2": {"pageid": 2, "title": "B", "index": 2, "extract": "bee", "fullurl": "https://en.wikipedia.org/wiki/B"},
            "1": {"pageid": 1, "title": "A", "index": 1, "extract": "ay", "fullurl": "https://en.wikipedia.org/wiki/A"}}}}
        fake = FakeHttp({"wikipedia.org": FakeResponse(json_data=payload)})
        with mock.patch("app.tools.wikipedia.client", return_value=fake):
            run = await execute(get_tool("wikipedia_lookup"), {"query": "letters"})
        self.assertTrue(run.ok, run.error)
        self.assertEqual([a["title"] for a in run.output.data["articles"]], ["A", "B"])
        self.assertEqual(run.output.sources[0].url, "https://en.wikipedia.org/wiki/A")

    async def test_wikipedia_no_hits(self):
        fake = FakeHttp({"wikipedia.org": FakeResponse(json_data={"batchcomplete": ""})})
        with mock.patch("app.tools.wikipedia.client", return_value=fake):
            run = await execute(get_tool("wikipedia_lookup"), {"query": "zzzzqq"})
        self.assertFalse(run.ok)
        self.assertIn("No Wikipedia article", run.error)

    async def test_hacker_news(self):
        payload = {"hits": [{"title": "Show HN: x", "url": None, "objectID": "42", "points": 10, "num_comments": 3, "created_at": "2026-01-02T00:00:00Z"}]}
        fake = FakeHttp({"algolia": FakeResponse(json_data=payload)})
        with mock.patch("app.tools.hacker_news.client", return_value=fake):
            run = await execute(get_tool("hacker_news_search"), {"query": "x402"})
        self.assertTrue(run.ok, run.error)
        self.assertEqual(run.output.data["stories"][0]["url"], "https://news.ycombinator.com/item?id=42")

    async def test_crypto(self):
        fake = FakeHttp({
            "/search": FakeResponse(json_data={"coins": [{"id": "ethereum", "symbol": "eth", "name": "Ethereum"}]}),
            "/simple/price": FakeResponse(json_data={"ethereum": {"usd": 3000.5, "usd_24h_change": 1.234, "usd_market_cap": 1e11}}),
        })
        with mock.patch("app.tools.crypto.client", return_value=fake):
            run = await execute(get_tool("crypto_price"), {"coins": ["ETH"]})
        self.assertTrue(run.ok, run.error)
        row = run.output.data["prices"][0]
        self.assertEqual((row["symbol"], row["price"], row["change_24h_pct"]), ("ETH", 3000.5, 1.23))

    async def test_crypto_rate_limited(self):
        fake = FakeHttp({"/search": FakeResponse(status=429)})
        with mock.patch("app.tools.crypto.client", return_value=fake):
            run = await execute(get_tool("crypto_price"), {"coins": ["btc"]})
        self.assertFalse(run.ok)
        self.assertIn("rate limit", run.error)

    async def test_web_search_duckduckgo_and_empty(self):
        html = '<a class="result__a" href="https://a.com/">A</a><a class="result__snippet">snip</a>'
        with mock.patch("app.tools.web_search.client", return_value=FakeHttp({"duckduckgo": FakeResponse(text=html)})):
            run = await execute(get_tool("web_search"), {"query": "hello world"})
        self.assertTrue(run.ok, run.error)
        self.assertEqual(run.output.data["provider"], "duckduckgo")
        with mock.patch("app.tools.web_search.client", return_value=FakeHttp({"duckduckgo": FakeResponse(text="<html></html>")})):
            run = await execute(get_tool("web_search"), {"query": "hello world"})
        self.assertFalse(run.ok)
        self.assertIn("No web results", run.error)

    async def test_fetch_webpage_blocks_internal_targets(self):
        for url in ["http://127.0.0.1/admin", "http://localhost:8080/", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.1/", "file:///etc/passwd"]:
            run = await execute(get_tool("fetch_webpage"), {"url": url})
            self.assertFalse(run.ok, url)

    async def test_fetch_webpage_reads_html_and_checks_redirect_hops(self):
        html = b"<html><title>T</title><body><p>Hello world</p></body></html>"
        page = FakeResponse(headers={"content-type": "text/html; charset=utf-8"}, body=html)
        fake = FakeHttp({"https://93.184.216.34/": page})
        with mock.patch("app.tools.webpage.client", return_value=fake):
            run = await execute(get_tool("fetch_webpage"), {"url": "https://93.184.216.34/"})
        self.assertTrue(run.ok, run.error)
        self.assertEqual(run.output.data["title"], "T")
        self.assertIn("Hello world", run.output.data["text"])
        # a public URL that redirects to an internal address must be refused
        redirect = FakeResponse(status=302, headers={"location": "http://127.0.0.1/secret"})
        fake = FakeHttp({"https://93.184.216.34/": redirect})
        with mock.patch("app.tools.webpage.client", return_value=fake):
            run = await execute(get_tool("fetch_webpage"), {"url": "https://93.184.216.34/"})
        self.assertFalse(run.ok)
        self.assertIn("Blocked", run.error)

    async def test_fetch_webpage_rejects_pdf(self):
        pdf = FakeResponse(headers={"content-type": "application/pdf"}, body=b"%PDF")
        with mock.patch("app.tools.webpage.client", return_value=FakeHttp({"https://93.184.216.34/": pdf})):
            run = await execute(get_tool("fetch_webpage"), {"url": "https://93.184.216.34/"})
        self.assertFalse(run.ok)
        self.assertIn("PDF", run.error)

    async def test_wallet_tool(self):
        wallet = {"exists": True, "address": "0x1234567890abcdef1234567890abcdef12345678", "network": "Base Sepolia", "eth": "0.01", "usdc": "5.0", "explorerUrl": "https://sepolia.basescan.org/address/0x1"}
        with mock.patch("app.tools.wallet.client", return_value=FakeHttp({"/api/wallet": FakeResponse(json_data=wallet)})):
            run = await execute(get_tool("get_wallet_info"), {})
        self.assertTrue(run.ok, run.error)
        self.assertEqual(run.output.data["eth_balance"], "0.01")
        self.assertNotIn("private", str(run.output.data).lower())
        with mock.patch("app.tools.wallet.client", return_value=FakeHttp({"/api/wallet": FakeResponse(json_data={"exists": False})})):
            run = await execute(get_tool("get_wallet_info"), {})
        self.assertTrue(run.ok)
        self.assertFalse(run.output.data["exists"])

    async def test_timeout_is_reported(self):
        import asyncio
        from app.tools.base import Tool, ToolOutput
        from app.tools.calculator import CalcArgs

        async def slow(_):
            await asyncio.sleep(1)
            return ToolOutput({}, "x")

        run = await execute(Tool("slow", "d", CalcArgs, slow), {"expression": "1"}, timeout_s=0.05)
        self.assertFalse(run.ok)
        self.assertIn("timed out", run.error)


if __name__ == "__main__":
    unittest.main()
