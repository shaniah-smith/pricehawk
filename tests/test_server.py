"""End-to-end tests over the MCP protocol, using demo data (no API keys needed)."""

import json

import pytest
from mcp import Client

from pricehawk import server


@pytest.fixture(autouse=True)
def demo_env(monkeypatch, tmp_path):
    for key in ("SERPAPI_KEY", "BESTBUY_API_KEY", "SHOPIFY_CLIENT_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PRICEHAWK_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("PRICEHAWK_MAX_ORDER", "100000")
    server._store = None
    server._offer_cache.clear()
    yield
    server._store = None


async def call(client, tool, **args):
    res = await client.call_tool(tool, args)
    assert not res.is_error, res
    if res.structured_content:
        data = res.structured_content
        return data.get("result", data)
    return json.loads(res.content[0].text)


async def test_lists_tools():
    async with Client(server.mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert {"compare_prices", "new_releases", "top_brands", "prepare_purchase", "confirm_purchase"} <= names


async def test_compare_prices_ranks_and_badges():
    async with Client(server.mcp) as c:
        out = await call(c, "compare_prices", query="wireless earbuds", max_results=5)
    assert out["sources"] == ["demo"]
    results = out["results"]
    assert len(results) == 5
    scores = [r["deal_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert "🔥 Best deal" in results[0]["badges"]
    assert out["table"].startswith("| # | Product")


async def test_budget_filter():
    async with Client(server.mcp) as c:
        out = await call(c, "compare_prices", query="desk lamp", max_price=60)
    assert all(r["price"] <= 60 for r in out["results"])


async def test_new_releases_and_brands():
    async with Client(server.mcp) as c:
        nr = await call(c, "new_releases", category="headphones", brand="Aurora", days=60)
        tb = await call(c, "top_brands", category="headphones")
    assert nr["results"] and all("Aurora" in r["title"] for r in nr["results"])
    assert tb["brands"] and "| Brand |" in tb["table"]


async def test_watchlist_flow():
    async with Client(server.mcp) as c:
        w = await call(c, "watch_price", query="gaming mouse", target_price=100000)
        check = await call(c, "check_watchlist")
        hist = await call(c, "price_history", query="gaming mouse")
        removed = await call(c, "unwatch_price", watch_id=w["watch_id"])
    assert check["target_hit"][0]["query"] == "gaming mouse"
    assert hist["history"]
    assert removed["removed"] is True


async def test_purchase_requires_confirmation():
    async with Client(server.mcp) as c:
        out = await call(c, "compare_prices", query="mechanical keyboard")
        pid = out["results"][0]["product_id"]
        prep = await call(c, "prepare_purchase", product_id=pid)
        assert prep["status"] == "awaiting_confirmation"
        refused = await call(c, "confirm_purchase", purchase_id=prep["purchase_id"], user_confirmed=False)
        assert "error" in refused
        done = await call(c, "confirm_purchase", purchase_id=prep["purchase_id"], user_confirmed=True)
        assert done["status"] == "demo_completed"
        again = await call(c, "confirm_purchase", purchase_id=prep["purchase_id"], user_confirmed=True)
        assert "error" in again
        log = await call(c, "purchase_log")
    assert log["purchases"][0]["status"] == "demo_completed"


async def test_spending_cap(monkeypatch):
    monkeypatch.setenv("PRICEHAWK_MAX_ORDER", "1")
    async with Client(server.mcp) as c:
        out = await call(c, "compare_prices", query="standing desk")
        prep = await call(c, "prepare_purchase", product_id=out["results"][0]["product_id"])
    assert "limit" in prep["error"]
