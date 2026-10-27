# PriceHawk demo guide

Two ways to show it. Do **A** live; keep **B** as the backup if the Wi-Fi or Claude is slow.

## Before you present (5 minutes)

1. Open the project in VS Code: `code ~/Downloads/pricehawk`
2. Run the tests once so you know everything is green: **Cmd+Shift+P → Tasks: Run Test Task**
3. Quit and reopen Claude Desktop so PriceHawk is connected. Do one warm-up question.
4. Make the VS Code terminal font big: it's set to 15 in `.vscode/settings.json`, bump it if the room is large.
5. Close anything with personal info (email, other chats).

## A. Live in Claude Desktop (about 4 minutes)

Say these in one new chat, in order:

| # | Type this | What to point out |
|---|---|---|
| 1 | *Use PriceHawk to find the best deal on noise-cancelling headphones under $300* | The AI picked the tool by itself. Ranked table, deal score, badges |
| 2 | *Is that actually a good price?* | Fake-sale check: compares today with past prices |
| 3 | *Did anything new come out in headphones in the last 60 days?* | New releases with 🆕 badges |
| 4 | *Which brands lead this category?* | Market overview for people who don't know the brands |
| 5 | *Watch the top pick and tell me if it drops 10%* | Price alerts, can run on a schedule |
| 6 | *Buy the best deal* | It **stops and asks you first**. Say yes. Demo order, no real money |

## B. Terminal walkthrough (backup, about 3 minutes)

In VS Code: **Cmd+Shift+P → Tasks: Run Task → Demo: walkthrough**, then press Enter between steps.

It launches the real server over MCP, exactly like Claude does, and runs all six steps above with a fresh database each time. Options:

```bash
python scripts/demo.py --query "gaming monitor" --budget 400
python scripts/demo.py --auto     # no pauses
python scripts/demo.py --real     # real store APIs (needs keys in .env)
```

## Talking points

- **Problem:** comparing prices means ten tabs, fake "sales", and no idea what's new.
- **What it is:** an MCP server, so it plugs into Claude, ChatGPT, VS Code Copilot, or any MCP client. Build once, works everywhere.
- **Deal score:** 55% price, 30% rating adjusted for review count, 15% discount. A 5.0 from 3 reviews doesn't beat a 4.7 from 2,000.
- **Data:** official APIs (Google Shopping via SerpAPI, Best Buy, Shopify), not scraping, so it doesn't break and respects store terms.
- **Buying:** uses Shopify's agent checkout (Universal Commerce Protocol). Two steps, a spending cap, an allowed-store list, and it never touches card numbers.
- **Engineering:** async calls to all sources at once, SQLite price history, provider plugin system, end-to-end tests over MCP.

## Likely questions

- **"Is this real data?"** Demo mode uses fictional stores so it runs anywhere. With API keys it switches to real stores automatically (`--real`).
- **"Can it buy from Amazon?"** No. Amazon blocks AI agents from purchasing. PriceHawk still compares Amazon prices and gives a link.
- **"What stops it from buying things on its own?"** The purchase is split in two, `confirm_purchase` requires explicit user confirmation, and there's a hard spending cap.
- **"How would you add a store?"** Subclass `Provider` in `src/pricehawk/providers/`, implement `search()`, register it. About 50 lines.
