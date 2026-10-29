"""eBay search results via SerpAPI (https://serpapi.com/ebay-search-api). New and used listings.

Reuses SERPAPI_KEY. Set PRICEHAWK_EBAY=0 to turn it off and save searches.
"""

from __future__ import annotations

from typing import Any

from ..models import Offer
from .base import Provider


def _price(p: Any) -> float | None:
    """eBay prices are either {"extracted": 9.99} or a range {"from": {...}, "to": {...}}."""
    if not isinstance(p, dict):
        return None
    value = p.get("extracted") or (p.get("from") or {}).get("extracted")
    return float(value) if value else None


class SerpApiEbayProvider(Provider):
    name = "ebay"
    URL = "https://serpapi.com/search.json"

    def enabled(self) -> bool:
        return self.env("SERPAPI_KEY") is not None and self.switch("PRICEHAWK_EBAY")

    async def _query(self, q: str, limit: int) -> list[Offer]:
        params = {"engine": "ebay", "_nkw": q, "ebay_domain": "ebay.com", "api_key": self.env("SERPAPI_KEY")}
        async with self.client() as c:
            r = await c.get(self.URL, params=params)
            r.raise_for_status()
            return self.parse(r.json(), limit)

    @classmethod
    def parse(cls, data: dict[str, Any], limit: int) -> list[Offer]:
        offers = []
        for item in data.get("organic_results", []):
            price = _price(item.get("price"))
            # Auction prices are just the current bid, so they would skew the comparison.
            if not price or item.get("buying_format") == "auction":
                continue
            title = item.get("title", "").strip()
            condition = item.get("condition")
            if condition and condition.lower() not in ("brand new", "new"):
                title = f"{title} ({condition})"
            offers.append(
                Offer(
                    title=title,
                    price=price,
                    regular_price=_price(item.get("old_price")),
                    store="eBay",
                    url=item.get("link") or "",
                    source=cls.name,
                    rating=item.get("rating"),
                    reviews=item.get("reviews"),
                    image=item.get("thumbnail"),
                )
            )
            if len(offers) >= limit:
                break
        return offers

    async def search(self, query: str, limit: int = 20) -> list[Offer]:
        return await self._query(query, limit)
