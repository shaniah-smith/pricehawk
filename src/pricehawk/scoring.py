"""Deal scoring, de-duplication and badges."""

from __future__ import annotations

import re
from datetime import date, timedelta

from .models import Offer

# Prior used to shrink ratings with few reviews toward an average product.
# A 5.0 from 3 reviews should not beat a 4.7 from 2,000.
PRIOR_RATING = 4.0
PRIOR_WEIGHT = 25
NEW_RELEASE_DAYS = 60


def trusted_rating(o: Offer) -> float | None:
    if o.rating is None:
        return None
    n = o.reviews or 0
    return (o.rating * n + PRIOR_RATING * PRIOR_WEIGHT) / (n + PRIOR_WEIGHT)


def _key(o: Offer) -> tuple[str, str]:
    title = re.sub(r"[^a-z0-9]+", " ", o.title.lower()).strip()
    return title, o.store.lower()


def dedupe(offers: list[Offer]) -> list[Offer]:
    """Keep the cheapest listing of the same product at the same store."""
    best: dict[tuple[str, str], Offer] = {}
    for o in offers:
        if o.price <= 0:
            continue
        k = _key(o)
        if k not in best or o.price < best[k].price:
            best[k] = o
    return list(best.values())


def score(offers: list[Offer], today: date | None = None) -> list[Offer]:
    """Give every offer a 0-100 deal score and badges, sorted best first.

    Score = 55% price (cheapest in the set scores highest)
          + 30% trusted rating
          + 15% discount off list price (capped at 40% off).
    """
    if not offers:
        return offers
    today = today or date.today()
    prices = sorted(o.price for o in offers)
    lo, hi = prices[0], prices[-1]
    span = hi - lo or 1.0

    for o in offers:
        price_part = 1 - (o.price - lo) / span
        tr = trusted_rating(o)
        rating_part = (tr / 5) if tr is not None else 0.6
        discount_part = min(o.discount / 0.4, 1.0)
        o.deal_score = round(100 * (0.55 * price_part + 0.30 * rating_part + 0.15 * discount_part), 1)
        o.badges = []

    offers.sort(key=lambda o: o.deal_score or 0, reverse=True)

    offers[0].badges.append("🔥 Best deal")
    min(offers, key=lambda o: o.price).badges.append("💸 Lowest price")
    rated = [o for o in offers if trusted_rating(o) is not None]
    if rated:
        max(rated, key=lambda o: trusted_rating(o) or 0).badges.append("⭐ Top rated")
    for o in offers:
        if o.discount >= 0.15:
            o.badges.append(f"🏷️ -{round(o.discount * 100)}%")
        if o.release_date and o.release_date >= today - timedelta(days=NEW_RELEASE_DAYS):
            o.badges.append("🆕 New")
    return offers


def fmt_money(amount: float, currency: str = "USD") -> str:
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$"}.get(currency, f"{currency} ")
    return f"{symbol}{amount:,.2f}"


def table(offers: list[Offer], limit: int = 10) -> str:
    """Markdown table the AI can show the user directly."""
    rows = ["| # | Product | Store | Price | Rating | Deal | Badges |", "|---|---|---|---|---|---|---|"]
    for i, o in enumerate(offers[:limit], 1):
        price = fmt_money(o.price, o.currency)
        if o.discount >= 0.05 and o.regular_price:
            price += f" ~~{fmt_money(o.regular_price, o.currency)}~~"
        rating = f"{o.rating:.1f} ({o.reviews or 0:,})" if o.rating is not None else "–"
        title = o.title if len(o.title) <= 60 else o.title[:57] + "…"
        rows.append(
            f"| {i} | [{title}]({o.url}) | {o.store} | {price} | {rating} | "
            f"{o.deal_score:.0f} | {' '.join(o.badges)} |"
        )
    return "\n".join(rows)
