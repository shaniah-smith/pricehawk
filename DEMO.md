# PriceHawk demo guide

Two ways to show it. Do **A** live; keep **B** as the backup if the Wi-Fi or Claude is slow.

## Before you present (5 minutes)

1. Open the `pricehawk` folder itself in VS Code (**File → Open Folder**), not a parent folder, or the tasks won't show up. The tasks work on Windows, macOS and Linux.
2. Run the tests once so you know everything is green: **Ctrl+Shift+P → Tasks: Run Test Task**
3. Check `.env` has your `SERPAPI_KEY`, and that your SerpAPI account has searches left (each question below uses about 3).
4. Quit and reopen Claude Desktop (or Claude Code) so PriceHawk is connected. Do one warm-up question.
5. Make the VS Code terminal font big: it's set to 15 in `.vscode/settings.json`, bump it if the room is large.
6. Close anything with personal info (email, other chats).

## A. Live in Claude (about 4 minutes)

Say these in one new chat, in order:

| # | Type this | What to point out |
|---|---|---|
| 1 | *Use PriceHawk to find the best deal on noise-cancelling headphones under $300* | The AI picked the tool by itself. Real listings from Google Shopping, Walmart and eBay in one ranked table, with deal scores and badges |
| 2 | *Is that actually a good price?* | Fake-sale check: compares today with past prices (gets smarter with every search) |
| 3 | *Did anything new come out in headphones recently?* | Newest listings from Walmart and Google Shopping |
| 4 | *Which brands lead this category?* | Market overview from real listings: Sony, Bose, JBL and so on |
| 5 | *Watch the top pick and tell me if it drops 10%* | Price alerts, can run on a schedule |
| 6 | *Where should I buy it?* | The store showdown: best pick at each store with a link. You check out on the store's own site |

## B. Terminal walkthrough (backup, about 3 minutes)

In VS Code: **Ctrl+Shift+P → Tasks: Run Task → Demo: walkthrough with live stores** (or **Demo: walkthrough** for demo data), then press Enter between steps.

It launches the real server over MCP, exactly like Claude does, and runs all six steps above with a fresh database each time. Options:

```bash
python scripts/demo.py --real     # live stores (uses about 9 searches)
python scripts/demo.py            # demo data, no internet or key needed: the safest backup
python scripts/demo.py --query "gaming monitor" --budget 400
python scripts/demo.py --auto     # no pauses
```

## Talking points

- **Problem:** comparing prices means ten tabs, fake "sales", and no idea what's new.
- **What it is:** an MCP server, so it plugs into Claude, ChatGPT, VS Code Copilot, or any MCP client. Build once, works everywhere.
- **Three stores, one key:** Google Shopping, Walmart and eBay searched at the same time through one SerpAPI key.
- **Deal score:** 55% price, 30% rating adjusted for review count, 15% discount. A 5.0 from 3 reviews doesn't beat a 4.7 from 2,000.
- **Honest data:** eBay used and open-box items are labelled, auctions are skipped, and demo data is always flagged as sample data.
- **Safe by design:** PriceHawk never buys anything or sees card details. It hands you the store's own link.
- **Engineering:** async calls to all stores at once, SQLite price history, provider plugin system, end-to-end tests over MCP.

## Likely questions

- **"Is this real data?"** Yes, with a key it's live Google Shopping, Walmart and eBay. Without a key it switches to clearly labelled demo data so it runs anywhere.
- **"Can it buy for me?"** On purpose, no. It finds the deal and gives you the link; checkout happens on the store's site. Many stores, Amazon included, block AI agents from buying anyway.
- **"Why are some discounts so big?"** Those are the stores' own "was" prices. Spotting inflated ones is next on the roadmap, and the fake-sale check already compares against real price history.
- **"How would you add a store?"** Subclass `Provider` in `src/pricehawk/providers/`, implement `search()`, register it. About 50 lines; SerpAPI already supports more stores with the same key.
