# 🦅 PriceHawk

[![tests](https://github.com/shaniah-smith/pricehawk/actions/workflows/tests.yml/badge.svg)](https://github.com/shaniah-smith/pricehawk/actions/workflows/tests.yml)

**An AI shopping scout for any MCP client.** Ask your AI *"what's the best deal on noise-cancelling headphones under $300?"* and PriceHawk searches **Google Shopping, Walmart and eBay at the same time**, ranks every listing with a deal score, tells you whether the "sale" is real, and hands you the link to buy it on the store's own site.

It runs on **one free API key** ([SerpAPI](https://serpapi.com)) and works with Claude Desktop, Claude Code, and any other client that speaks the [Model Context Protocol](https://modelcontextprotocol.io).

## What it can do

| Tool | What it does |
|---|---|
| `compare_prices` | Searches Google Shopping, Walmart and eBay in parallel, removes duplicates, and ranks results by a 0–100 **deal score** |
| ↳ store showdown | The same call returns `best_by_store`: the top pick at each store with its buy link, for "where should I buy this?" |
| `price_history` | Daily lows over time plus a **fake-sale check** ("is this 'sale' actually low?") |
| `new_releases` | Recently listed products in a category, optionally from one brand |
| `top_brands` | Which brands lead a category by number of listings, typical price, and rating |
| `watch_price` / `check_watchlist` | Get alerted when something drops to your target price |
| `list_watchlist` / `unwatch_price` | Manage your alerts |

Every result gets badges: 🔥 Best deal · 💸 Lowest price · ⭐ Top rated · 🏷️ −25% · 🆕 New

### What each store adds

| Store | What you get |
|---|---|
| **Google Shopping** | Prices from many retailers in one search (Target, Amazon listings, brand stores and more) |
| **Walmart** | Walmart prices, ratings and review counts, and "was" prices so discounts are visible. Its newest listings feed `new_releases` |
| **eBay** | New, open-box and used prices. Non-new items are labelled, for example "(Open Box)" or "(Pre-Owned)". Auctions are skipped because a current bid isn't a real price |

### How the deal score works

```
deal score = 55% price      (cheapest in the set scores highest)
           + 30% rating     (adjusted for review count, so a 5.0 from 3 reviews ranks below a 4.7 from 2,000)
           + 15% discount   (off the list price, capped at 40%)
```

### Buying

PriceHawk **never buys anything or touches payment details**. Every listing comes with a link to the store's own page, and you check out there. That keeps it simple and safe, and it works for every store, including the ones that block AI agents from purchasing.

## Quick start

### 1. Install

```bash
git clone https://github.com/shaniah-smith/pricehawk.git
cd pricehawk
pip install -e .
```

### 2. Add your key (optional, but this is where it comes alive)

```bash
cp .env.example .env     # then open .env and paste your SERPAPI_KEY
```

Get a free key at [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). PriceHawk reads `.env` from the current folder or the project root when the server starts. `.env` is git-ignored, so never put real keys in `.env.example`.

**No key?** PriceHawk runs in **demo mode** with sample data (fictional stores and brands), so you can try every tool right away.

### 3. Run it

```bash
pricehawk          # starts the MCP server over stdio
```

### See the whole thing in 3 minutes

```bash
python scripts/demo.py            # demo data, no API calls
python scripts/demo.py --real     # live Google Shopping, Walmart and eBay
```

A guided walkthrough of every feature over the real MCP protocol: compare, fake-sale check, new releases, top brands, price alert, and the store showdown. See [DEMO.md](DEMO.md) for a presentation guide.

### Connect it to Claude Code

```bash
claude mcp add pricehawk -- pricehawk
```

Then try: *"Use PriceHawk to find the best deal on a mechanical keyboard under $150."*

### Connect it to Claude Desktop

Add this to `claude_desktop_config.json` (see [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json)). You can paste the key here or leave it blank to use `.env`:

```json
{
  "mcpServers": {
    "pricehawk": {
      "command": "pricehawk",
      "env": { "SERPAPI_KEY": "" }
    }
  }
}
```

## Settings

| Variable | Default | What it does |
|---|---|---|
| `SERPAPI_KEY` | (blank) | Turns on Google Shopping, Walmart and eBay. Blank = demo mode |
| `PRICEHAWK_WALMART` | `1` | `0` turns Walmart off |
| `PRICEHAWK_EBAY` | `1` | `0` turns eBay off |
| `PRICEHAWK_DEMO` | (blank) | Blank = demo data only when there's no key. `1` = always mix it in. `0` = never |
| `PRICEHAWK_COUNTRY` | `us` | Google Shopping country |
| `PRICEHAWK_DB` | `~/.pricehawk/pricehawk.db` | Where price history and the watchlist live |
| `PRICEHAWK_DOTENV` | (on) | `0` skips reading `.env` |

Values already set in your environment (or a Claude Desktop `env` block) take priority over `.env`; blank ones are filled from it.

**Search budget:** each store uses one SerpAPI search per lookup, so a `compare_prices` call costs 3 searches and the full demo walkthrough about 9. Turn off a store you don't need to make the free tier last longer.

PriceHawk uses official search APIs instead of scraping store pages, which breaks often and is prohibited by many retailers' terms of service.

## Daily deal alerts

Ask your AI to run `check_watchlist` on a schedule (for example, every morning). It reports which watched items hit your target price, with the store and the link to buy.

> *"Watch noise cancelling headphones and tell me when the best deal is under $40."*

## Project layout

```
src/pricehawk/
  server.py             MCP tools, prompt and resource; loads .env
  scoring.py            deal score, de-duplication, badges, markdown table
  store.py              SQLite price history and watchlist
  providers/
    serpapi.py          Google Shopping
    serpapi_walmart.py  Walmart
    serpapi_ebay.py     eBay
    demo.py             sample data (no key)
scripts/demo.py         guided terminal demo
tests/                  end-to-end tests over the MCP protocol, plus provider parsing tests
.vscode/                interpreter, test, task and debug setup for VS Code
```

## Working in VS Code

Open the folder (`code .`), accept the recommended extensions, then use **Ctrl+Shift+P → Tasks: Run Task**:

- **Setup: create venv and install**
- **Demo: walkthrough**
- **Run tests**
- **MCP Inspector**: click through every tool in a browser (needs Node.js)

## Development

```bash
pip install -e ".[dev]"
pytest
```

Add a store by subclassing `Provider` in `providers/` (implement `enabled()` and `search()`, plus `new_releases()` if the source can sort by newest) and registering it in `providers/__init__.py`. SerpAPI covers more stores with the same key (for example Home Depot), so most new stores are about 50 lines like [`serpapi_walmart.py`](src/pricehawk/providers/serpapi_walmart.py).

## Roadmap

- Smarter discount scoring, so inflated "was" prices can't push a listing to the top
- Merge the same product listed under several item IDs at one store
- More stores through SerpAPI (Home Depot, more countries)
- Interactive comparison card (MCP Apps UI)
- Push notifications for watchlist hits

## Changelog

### Unreleased: live sources remodel
- **Added Walmart and eBay** through SerpAPI. One `SERPAPI_KEY` now powers three live stores, with `PRICEHAWK_WALMART` / `PRICEHAWK_EBAY` switches.
- **Added the store showdown**: `compare_prices` returns `best_by_store`, the top pick at each store with its link.
- **Added `.env` support**: the server loads keys from `.env` at startup.
- **Removed Shopify checkout and the purchase tools** (`prepare_purchase`, `confirm_purchase`, `cancel_purchase`, `purchase_log`) and their settings (`PRICEHAWK_MAX_ORDER`, `PRICEHAWK_ALLOWED_STORES`, `PRICEHAWK_BUYER_EMAIL`). Shopify's agent checkout wasn't available to us, so buying now means a link to the store's own checkout.
- **Removed the Best Buy source**: Best Buy only issues API keys to business email addresses.
- Removed an exposed API key from `.env.example`.
- `scripts/demo.py` ignores `.env` in demo mode so it never spends real searches.

## License

MIT
