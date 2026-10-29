"""Walmart search results via SerpAPI (https://serpapi.com/walmart-search-api).

Reuses SERPAPI_KEY. Set PRICEHAWK_WALMART=0 to turn it off and save searches.
"""

from __future__ import annotations

from typing import Any

from ..models import Offer
from .base import Provider


class SerpApiWalmartProvider(Provider):
    name = "walmart"
    URL = "https://serpapi.com/search.json"

    def enabled(self) -> bool:
        return self.env("SERPAPI_KEY") is not None and self.switch("PRICEHAWK_WALMART")

    async def _query(self, q: str, limit: int, sort: str | None = None) -> list[Offer]:
        params = {"engine": "walmart", "query": q, "api_key": self.env("SERPAPI_KEY")}
        if sort:
            params["sort"] = sort
        async with self.client() as c:
            r = await c.get(self.URL, params=params)
            r.raise_for_status()
            return self.parse(r.json(), limit)

    @classmethod
    def parse(cls, data: dict[str, Any], limit: int) -> list[Offer]:
        offers = []
        for item in data.get("organic_results", []):
            offer = item.get("primary_offer") or {}
            price = offer.get("offer_price")
            if not price or item.get("out_of_stock"):
                continue
            offers.append(
                Offer(
                    title=item.get("title", "").strip(),
                    price=float(price),
                    regular_price=offer.get("was_price") or None,
                    store="Walmart",
                    url=item.get("product_page_url") or "",
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

    async def new_releases(self, category: str, brand: str | None, days: int, limit: int = 20) -> list[Offer]:
        # Walmart has no release-date filter, but it can sort by newest listings.
        return await self._query(f"{brand or ''} {category}".strip(), limit, sort="new")
