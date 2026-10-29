"""PriceHawk MCP server: an AI shopping scout.

Tools:
  compare_prices   search every configured source, de-duplicate, rank by deal score
  new_releases     products that launched recently in a category / from a brand
  top_brands       which brands lead a category (listings, prices, ratings)
  price_history    daily lows over time + a fake-sale check
  watch_price / check_watchlist / list_watchlist / unwatch_price

Sources: Google Shopping, Walmart and eBay (all via one SerpAPI key), or demo data with no key.
"""

from __future__ import annotations

import asyncio
import logging
import os
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .models import Offer
from .providers import Provider, active_providers
from .scoring import dedupe, fmt_money, score, table, trusted_rating
from .store import Store

log = logging.getLogger("pricehawk")

INSTRUCTIONS = """PriceHawk compares prices across Google Shopping, Walmart and eBay, finds new
releases, checks whether a sale is real and tracks prices. Show results to the user as the
markdown table returned in `table`. PriceHawk never buys anything: when the user wants to buy,
give them the listing's `url` so they can check out on the store's own site.
If results come from the `demo` source, tell the user they are sample data."""

mcp = MCPServer("PriceHawk", instructions=INSTRUCTIONS)

_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


async def _gather(providers: list[Provider], fn: str, *args: Any) -> tuple[list[Offer], list[str]]:
    """Run the same call on every provider at once; collect offers and any errors."""
    results = await asyncio.gather(*(getattr(p, fn)(*args) for p in providers), return_exceptions=True)
    offers: list[Offer] = []
    errors: list[str] = []
    for p, r in zip(providers, results):
        if isinstance(r, BaseException):
            log.warning("%s failed: %s", p.name, r)
            errors.append(f"{p.name}: {type(r).__name__}: {r}")
        else:
            offers.extend(r)
    return offers, errors


def _best_by_store(offers: list[Offer], limit: int = 8) -> list[dict[str, Any]]:
    """Top-scoring listing at each store (offers must already be scored and sorted)."""
    seen: dict[str, Offer] = {}
    for o in offers:
        seen.setdefault(o.store, o)
    return [
        {"store": o.store, "title": o.title, "price": o.price, "deal_score": o.deal_score, "url": o.url}
        for o in list(seen.values())[:limit]
    ]


def _sources(offers: list[Offer], errors: list[str]) -> dict[str, Any]:
    used = sorted({o.source for o in offers})
    out: dict[str, Any] = {"sources": used}
    if "demo" in used:
        out["note"] = "Includes SAMPLE data from the demo source (fictional stores and brands)."
    if errors:
        out["source_errors"] = errors
    return out


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def compare_prices(
    query: str,
    max_results: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
) -> dict[str, Any]:
    """Compare prices for a product across every configured store and rank the deals.

    Each result gets a 0-100 deal score (price, review-weighted rating, discount) and badges
    such as Best deal, Lowest price, Top rated, -25% and New. Every result has a `url` to the
    store's own page, which is where the user buys it. `best_by_store` lists the top pick at
    each store, for "where should I buy this?" questions.

    Args:
        query: What to look for, e.g. "Sony WH-1000XM6" or "noise cancelling headphones".
        max_results: How many ranked results to return (1-30).
        min_price: Optional lower price bound.
        max_price: Optional upper price bound (the user's budget).
    """
    max_results = max(1, min(max_results, 30))
    offers, errors = await _gather(active_providers(), "search", query, 40)
    offers = dedupe(offers)
    if min_price is not None:
        offers = [o for o in offers if o.price >= min_price]
    if max_price is not None:
        offers = [o for o in offers if o.price <= max_price]
    if not offers:
        return {"query": query, "results": [], "message": "No listings found. Try a broader search.", **_sources(offers, errors)}

    score(offers)
    store().log_prices(query, offers)
    best, cheapest = offers[0], min(offers, key=lambda o: o.price)
    out: dict[str, Any] = {
        "query": query,
        "summary": (
            f"{len(offers)} listings. Best deal: {best.title} at {best.store} for "
            f"{fmt_money(best.price, best.currency)} (score {best.deal_score:.0f}). Lowest price: "
            f"{fmt_money(cheapest.price, cheapest.currency)} at {cheapest.store}."
        ),
        "table": table(offers, max_results),
        "results": [o.to_dict() for o in offers[:max_results]],
        "best_by_store": _best_by_store(offers),
    }
    check = store().sale_check(query, cheapest.price)
    if check:
        out["price_check"] = check
    out.update(_sources(offers, errors))
    return out


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def new_releases(category: str, brand: str | None = None, days: int = 60, max_results: int = 10) -> dict[str, Any]:
    """Find products that came out recently in a category, optionally from one brand.

    Args:
        category: e.g. "headphones", "laptops", "running shoes".
        brand: Optional brand, e.g. "Sony".
        days: How far back counts as new (default 60).
        max_results: How many to return (1-30).
    """
    max_results = max(1, min(max_results, 30))
    offers, errors = await _gather(active_providers(), "new_releases", category, brand, days, 40)
    offers = dedupe(offers)
    if not offers:
        return {"category": category, "results": [], "message": "No recent releases found.", **_sources(offers, errors)}
    score(offers)
    offers.sort(key=lambda o: (o.release_date is not None, o.release_date), reverse=True)
    return {
        "category": category,
        "brand": brand,
        "window_days": days,
        "table": table(offers, max_results),
        "results": [o.to_dict() for o in offers[:max_results]],
        **_sources(offers, errors),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def top_brands(category: str, max_results: int = 8) -> dict[str, Any]:
    """Rank the leading brands in a category by listings, typical price and rating.

    Useful when the user doesn't know the market yet ("who makes good espresso machines?").

    Args:
        category: e.g. "espresso machines".
        max_results: How many brands to return.
    """
    offers, errors = await _gather(active_providers(), "search", category, 60)
    offers = dedupe(offers)
    groups: dict[str, list[Offer]] = defaultdict(list)
    for o in offers:
        brand = o.brand or (o.title.split()[0] if o.title else None)
        if brand:
            groups[brand.strip().title()].append(o)
    rows = []
    for brand, items in groups.items():
        rated = [r for r in (trusted_rating(o) for o in items) if r is not None]
        rows.append(
            {
                "brand": brand,
                "listings": len(items),
                "median_price": round(statistics.median(o.price for o in items), 2),
                "price_range": [round(min(o.price for o in items), 2), round(max(o.price for o in items), 2)],
                "avg_rating": round(statistics.mean(rated), 2) if rated else None,
            }
        )
    rows.sort(key=lambda r: (r["listings"], r["avg_rating"] or 0), reverse=True)
    rows = rows[:max_results]
    md = ["| Brand | Listings | Median price | Range | Avg rating |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(
            f"| {r['brand']} | {r['listings']} | ${r['median_price']:,.2f} | "
            f"${r['price_range'][0]:,.0f}–${r['price_range'][1]:,.0f} | {r['avg_rating'] or '–'} |"
        )
    return {"category": category, "table": "\n".join(md), "brands": rows, **_sources(offers, errors)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def price_history(query: str, days: int = 90) -> dict[str, Any]:
    """Show the daily lowest price PriceHawk has seen for a search, and whether today's price is
    actually a good deal (fake-sale check). History builds up each time compare_prices runs.

    Args:
        query: The same search text used with compare_prices.
        days: How many days back to look.
    """
    lows = store().daily_lows(query, days)
    if not lows:
        return {"query": query, "history": [], "message": "No history yet. Run compare_prices first; history builds up over time."}
    out: dict[str, Any] = {"query": query, "history": lows, "all_time_low": min(r["low"] for r in lows)}
    check = store().sale_check(query, lows[-1]["low"])
    if check:
        out["price_check"] = check
    return out


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


@mcp.tool()
async def watch_price(query: str, target_price: float) -> dict[str, Any]:
    """Add a product to the watchlist; check_watchlist reports when it drops to the target.

    Args:
        query: What to watch, e.g. "AirPods Pro 3".
        target_price: Alert when the best price is at or below this.
    """
    wid = store().watch(query, target_price)
    return {"watch_id": wid, "message": f"Watching '{query}' for {fmt_money(target_price)} or less."}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_watchlist() -> dict[str, Any]:
    """List everything on the watchlist."""
    return {"watchlist": store().watches()}


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def unwatch_price(watch_id: int) -> dict[str, Any]:
    """Remove an item from the watchlist.

    Args:
        watch_id: The id from list_watchlist.
    """
    return {"removed": store().unwatch(watch_id)}


@mcp.tool(annotations=ToolAnnotations(openWorldHint=True))
async def check_watchlist() -> dict[str, Any]:
    """Re-check every watched product now and report which ones hit their target price.
    Good to run on a daily schedule."""
    watches = store().watches()
    hits, others = [], []
    for w in watches:
        res = await compare_prices(w["query"], max_results=3)
        results = res.get("results") or []
        if not results:
            others.append({"watch_id": w["id"], "query": w["query"], "status": "no listings found"})
            continue
        cheapest = min(results, key=lambda r: r["price"])
        store().update_watch(w["id"], cheapest["price"])
        entry = {
            "watch_id": w["id"],
            "query": w["query"],
            "target": w["target"],
            "best_price": cheapest["price"],
            "store": cheapest["store"],
            "url": cheapest["url"],
            "change_since_last_check": (
                round(cheapest["price"] - w["last_best"], 2) if w.get("last_best") is not None else None
            ),
        }
        (hits if cheapest["price"] <= w["target"] else others).append(entry)
    return {
        "checked": len(watches),
        "target_hit": hits,
        "not_yet": others,
        "message": (
            f"{len(hits)} item(s) hit the target price." if hits else "Nothing has hit its target yet."
        ),
    }


# ---------------------------------------------------------------------------
# Prompt + resource
# ---------------------------------------------------------------------------


@mcp.prompt()
def shopping_assistant(item: str, budget: str = "") -> str:
    """Find the best deal on something, check what's new, and offer to watch the price."""
    budget_line = f" My budget is {budget}." if budget else ""
    return (
        f"I'm shopping for {item}.{budget_line} Use PriceHawk to: 1) compare prices and show the ranked "
        "table, 2) check for anything released in the last 60 days I should consider, 3) tell me if "
        "the best price is genuinely low, and 4) offer to watch the price. When I pick one, give me "
        "the store link."
    )


@mcp.resource("pricehawk://watchlist")
def watchlist_resource() -> str:
    """The current watchlist as text."""
    rows = store().watches()
    if not rows:
        return "Watchlist is empty."
    return "\n".join(f"#{w['id']} {w['query']} → target ${w['target']:,.2f}" for w in rows)


def load_dotenv() -> None:
    """Fill unset (or blank) env vars from a .env file in the current folder or the project root.
    Values already set in the environment win. PRICEHAWK_DOTENV=0 skips this."""
    if os.environ.get("PRICEHAWK_DOTENV", "").strip().lower() in ("0", "false", "no"):
        return
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("\"'")
            if sep and key and not key.startswith("#") and value and not os.environ.get(key, "").strip():
                os.environ[key] = value
        return


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=os.environ.get("PRICEHAWK_LOG", "WARNING"))
    transport = os.environ.get("PRICEHAWK_TRANSPORT", "stdio")
    mcp.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
