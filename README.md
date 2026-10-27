# 🦅 PriceHawk

**An AI shopping scout for any MCP client.** Ask your AI *"what's the best deal on noise-cancelling headphones under $300, and is anything new coming out?"* and PriceHawk checks multiple stores at once, ranks the deals, spots new releases, tracks prices over time, and can prepare the purchase. Nothing is bought until you say yes.

Works with Claude Desktop, Claude Code, and any other client that speaks the [Model Context Protocol](https://modelcontextprotocol.io).

## What it can do

| Tool | What it does |
|---|---|
| `compare_prices` | Searches every configured source in parallel, removes duplicate listings, and ranks results by a 0–100 **deal score** |
| `new_releases` | Products that launched recently in a category, optionally from one brand |
| `top_brands` | Which brands lead a category by number of listings, typical price, and rating |
| `price_history` | Daily lows over time plus a **fake-sale check** ("is this 'sale' actually low?") |
| `watch_price` / `check_watchlist` | Get alerted when something drops to your target price |
| `prepare_purchase` → `confirm_purchase` | Two-step buying through Shopify agent checkout, with spending limits |

Every result gets badges: 🔥 Best deal · 💸 Lowest price · ⭐ Top rated · 🏷️ −25% · 🆕 New · 🛒 Buy in chat

### How the deal score works

```
deal score = 55% price      (cheapest in the set scores highest)
           + 30% rating     (adjusted for review count, so a 5.0 from 3 reviews ranks below a 4.7 from 2,000)
           + 15% discount   (off the list price, capped at 40%)
```

## Quick start (no API keys needed)

With no keys set, PriceHawk runs in **demo mode** using sample data (fictional stores and brands), so you can try the whole flow, including a demo purchase, right away.

```bash
git clone https://github.com/shaniah-smith/pricehawk.git
cd pricehawk
pip install -e .
pricehawk          # starts the MCP server over stdio
```

### Connect it to Claude Desktop

Add this to `claude_desktop_config.json` (see [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json)):

```json
{
  "mcpServers": {
    "pricehawk": {
      "command": "pricehawk",
      "env": {
        "SERPAPI_KEY": "",
        "BESTBUY_API_KEY": ""
      }
    }
  }
}
```

### Connect it to Claude Code

```bash
claude mcp add pricehawk -- pricehawk
```

Then try: *"Use PriceHawk to find the best deal on a mechanical keyboard under $150."*

## Data sources

Real sources turn on automatically when their keys are set. PriceHawk uses official APIs instead of scraping store pages, which breaks often and is prohibited by many retailers' terms of service.

| Source | Env vars | Good for |
|---|---|---|
| **Google Shopping** via [SerpAPI](https://serpapi.com) | `SERPAPI_KEY` | Prices across many stores in one call |
| **Best Buy** [Products API](https://developer.bestbuy.com) (free) | `BESTBUY_API_KEY` | Exact release dates, so `new_releases` is precise |
| **Shopify** [Catalog + Checkout MCP](https://shopify.dev/docs/agents) | `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_CATALOG_URL`, `SHOPIFY_AGENT_PROFILE` | Millions of Shopify stores, **and buying** |
| Demo | `PRICEHAWK_DEMO=1` to force on, `0` to force off | Trying it out |

Copy `.env.example` for the full list of settings.

## Buying safely

Purchases always take two steps, and the AI is told to ask you before the second one:

1. **`prepare_purchase`** creates a checkout and returns the item, store, and total. No order is placed.
2. You say yes in the chat.
3. **`confirm_purchase`** hands you the store's secure checkout link, already filled in, where you tap to pay.

Guardrails:
- **PriceHawk never sees or stores card details.** Payment happens on the merchant's own checkout page.
- `PRICEHAWK_MAX_ORDER` caps any single order (default `$500`).
- `PRICEHAWK_ALLOWED_STORES` limits buying to stores you trust.
- `purchase_log` keeps a record of everything prepared, confirmed, or canceled.
- Stores outside Shopify's agent checkout (for example, Amazon, which blocks AI agents from buying) get a regular "buy here" link instead.

### Shopify setup

1. Create a catalog in the Shopify **Dev Dashboard** and copy its client ID, client secret, and catalog URL.
2. Host a UCP agent profile ([guide](https://shopify.dev/docs/agents/get-started/profile)) and set `SHOPIFY_AGENT_PROFILE` to its URL.
3. Set `PRICEHAWK_BUYER_EMAIL` to the email used for orders.

## Daily deal alerts

Ask your AI to run `check_watchlist` on a schedule (for example, every morning). It reports which watched items hit your target price, and those results include a `product_id` you can pass straight to `prepare_purchase`.

> *"Watch the Sony WH-1000XM6 and tell me when it's under $280."*

## Project layout

```
src/pricehawk/
  server.py          MCP tools, prompt and resource
  scoring.py         deal score, de-duplication, badges, markdown table
  store.py           SQLite price history, watchlist, purchase log
  providers/
    demo.py          sample data (no keys)
    serpapi.py       Google Shopping
    bestbuy.py       Best Buy Products API
    shopify.py       Shopify Catalog + Checkout (UCP over MCP)
tests/               end-to-end tests over the MCP protocol
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

Add a new store by subclassing `Provider` in `providers/` (implement `enabled()` and `search()`, plus `new_releases()` if the source knows release dates) and registering it in `providers/__init__.py`.

## Roadmap

- eBay Browse API for used and refurbished prices
- Interactive comparison card (MCP Apps UI)
- Push notifications for watchlist hits
- Coupon and cashback lookup

## License

MIT
