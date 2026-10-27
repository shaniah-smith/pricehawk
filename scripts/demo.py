#!/usr/bin/env python3
"""PriceHawk live demo: walks through every feature over the real MCP protocol.

Runs the server exactly the way Claude Desktop does (a subprocess speaking MCP over stdio),
so what you show is the real thing, not a mock.

    python scripts/demo.py                 # press Enter between steps (good for presenting)
    python scripts/demo.py --auto          # run straight through
    python scripts/demo.py --query "gaming monitor" --budget 400
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp import Client  # noqa: E402
from mcp.client.stdio import StdioServerParameters  # noqa: E402

from pricehawk.store import Store  # noqa: E402

# ---- tiny terminal styling -------------------------------------------------

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


BOLD, DIM, GOLD, GREEN, CYAN, RED = "1", "2", "38;5;214", "38;5;42", "38;5;45", "38;5;203"

BANNER = r"""
   ____       _          _   _                _
  |  _ \ _ __(_) ___ ___| | | | __ ___      _| | __
  | |_) | '__| |/ __/ _ \ |_| |/ _` \ \ /\ / / |/ /
  |  __/| |  | | (_|  __/  _  | (_| |\ V  V /|   <
  |_|   |_|  |_|\___\___|_| |_|\__,_| \_/\_/ |_|\_\
"""


class Presenter:
    def __init__(self, auto: bool):
        self.auto = auto
        self.step = 0

    def title(self, text: str, say: str) -> None:
        self.step += 1
        print()
        print(c(f"━━ Step {self.step}: {text} ", GOLD + ";" + BOLD) + c("━" * max(0, 60 - len(text)), GOLD))
        print(c(f'   You say: "{say}"', CYAN))
        print()

    def pause(self) -> None:
        if self.auto:
            time.sleep(0.6)
        else:
            input(c("\n   ⏎  Enter for the next step", DIM))

    @staticmethod
    def tool(name: str, args: dict) -> None:
        shown = ", ".join(f"{k}={v!r}" for k, v in args.items())
        print(c(f"   ⚙  AI calls PriceHawk → {name}({shown})", DIM))
        print()


def body(text: str, indent: str = "   ") -> None:
    for line in text.splitlines():
        print(indent + line)


async def call(client: Client, p: Presenter, name: str, **args) -> dict:
    p.tool(name, args)
    res = await client.call_tool(name, args)
    data = res.structured_content or {}
    data = data.get("result", data)
    if res.is_error:
        raise RuntimeError(res.content[0].text if res.content else "tool error")
    return data


def seed_history(db_path: str, query: str, around: float) -> None:
    """Fill 30 days of past prices (demo only) so the fake-sale check has something to compare."""
    store = Store(db_path)
    r = random.Random(query)
    now = time.time()
    rows = []
    for day in range(30, 0, -1):
        low = round(around * r.uniform(1.12, 1.30), 2)
        rows.append((now - day * 86400, " ".join(query.lower().split()), "history", "history", low, "demo"))
    store.db.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?)", rows)
    store.db.commit()


async def run(args: argparse.Namespace) -> None:
    p = Presenter(args.auto)
    db = os.path.join(tempfile.mkdtemp(prefix="pricehawk-demo-"), "demo.db")
    env = {**os.environ, "PRICEHAWK_DB": db}
    if args.real:
        env.pop("PRICEHAWK_DEMO", None)
    else:
        for key in ("SERPAPI_KEY", "BESTBUY_API_KEY", "SHOPIFY_CLIENT_ID"):
            env.pop(key, None)
        env["PRICEHAWK_DEMO"] = "1"

    print(c(BANNER, GOLD + ";" + BOLD))
    print(c("   An AI shopping scout, plugged into any AI assistant through MCP.", BOLD))
    print(c(f"   Data: {'REAL store APIs' if args.real else 'demo mode (fictional stores and brands)'}", DIM))

    server = StdioServerParameters(command=sys.executable, args=["-m", "pricehawk"], env=env, cwd=str(ROOT))
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
        print(c(f"\n   ✓ Connected over MCP. The AI now has {len(tools)} PriceHawk tools:", GREEN))
        body(c(", ".join(t.name for t in tools), DIM), "     ")
        p.pause()

        # 1. Compare prices
        q, budget = args.query, args.budget
        p.title("Compare prices across stores", f"Find me the best deal on {q} under ${budget:g}")
        out = await call(client, p, "compare_prices", query=q, max_results=6, max_price=budget)
        body(c(out.get("summary", ""), BOLD))
        print()
        body(out.get("table", ""))
        best = out["results"][0]
        p.pause()

        # 2. Fake-sale check
        if not args.real:
            seed_history(db, q, best["price"])
        p.title("Is this sale real?", "Is that actually a good price?")
        hist = await call(client, p, "price_history", query=q, days=30)
        check = hist.get("price_check")
        if check:
            arrow = c(f"{check['change_pct']:+.1f}%", GREEN if check["change_pct"] < 0 else RED)
            body(f"Typical low over 30 days: ${check['typical_30d_low']:,.2f}   Today vs typical: {arrow}")
            body(c(f"Verdict: {check['verdict']}", BOLD))
        else:
            body("Not enough history yet. PriceHawk logs every search, so this gets smarter daily.")
        p.pause()

        # 3. New releases
        category = args.category or q
        p.title("What's new?", f"Did anything new come out in {category} recently?")
        nr = await call(client, p, "new_releases", category=category, days=60, max_results=5)
        body(nr.get("table", "No recent releases found."))
        p.pause()

        # 4. Top brands
        p.title("Who leads the market?", f"Which brands are best for {category}?")
        tb = await call(client, p, "top_brands", category=category, max_results=5)
        body(tb.get("table", ""))
        p.pause()

        # 5. Watchlist
        target = round(best["price"] * 0.9, 2)
        p.title("Price alerts", f"Tell me when it drops below ${target:,.2f}")
        w = await call(client, p, "watch_price", query=q, target_price=target)
        body(c("✓ " + w["message"], GREEN))
        body(c("Run check_watchlist on a daily schedule to get pinged when it hits.", DIM))
        p.pause()

        # 6. Buy with confirmation
        p.title("Buy it, safely", "Buy the best deal")
        prep = await call(client, p, "prepare_purchase", product_id=best["product_id"])
        if "error" in prep:
            body(c(prep["error"], RED))
        else:
            body(c(f"🛒 {prep['summary']}", BOLD))
            body(c("Status: awaiting your confirmation. Nothing has been bought yet.", DIM))
            print()
            body(c('AI: "Want me to place this order?"', CYAN))
            if p.auto:
                answer = "yes"
            else:
                answer = input(c("   You (yes/no): ", CYAN)).strip().lower() or "yes"
            print()
            if answer.startswith("y"):
                done = await call(client, p, "confirm_purchase", purchase_id=prep["purchase_id"], user_confirmed=True)
                body(c(f"✓ {done.get('message', done.get('status'))}", GREEN))
                if done.get("order_number"):
                    body(f"Order number: {done['order_number']}")
            else:
                await call(client, p, "cancel_purchase", purchase_id=prep["purchase_id"])
                body(c("✓ Canceled. No order placed.", GREEN))
        print()
        body(c("Guardrails: spending cap, allowed-store list, purchase log, and no card details", DIM))
        body(c("ever touch PriceHawk. Payment happens on the store's own checkout page.", DIM))

    print()
    print(c("━" * 72, GOLD))
    print(c("   That's PriceHawk: compare → verify → discover → watch → buy.", BOLD))
    print(c("   github.com/shaniah-smith/pricehawk", CYAN))
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", default="noise cancelling headphones")
    ap.add_argument("--budget", type=float, default=300)
    ap.add_argument("--category", default=None, help="category for new releases / top brands (default: the query)")
    ap.add_argument("--auto", action="store_true", help="don't pause between steps")
    ap.add_argument("--real", action="store_true", help="use real store APIs from your environment instead of demo data")
    try:
        asyncio.run(run(ap.parse_args()))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
