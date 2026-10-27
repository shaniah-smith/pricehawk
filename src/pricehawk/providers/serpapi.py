"""Google Shopping results via SerpAPI (https://serpapi.com). Covers many stores in one call.

Needs SERPAPI_KEY.
"""

from __future__ import annotations

from ..models import Offer
from .base import Provider


class SerpApiProvider(Provider):
    name = "serpapi"
    URL = "https://serpapi.com/search.json"

    def enabled(self) -> bool:
        return self.env("SERPAPI_KEY") is not None

    async def _query(self, q: str, limit: int) -> list[Offer]:
        params = {
            "engine": "google_shopping",
            "q": q,
            "gl": self.env("PRICEHAWK_COUNTRY") or "us",
            "hl": "en",
            "num": min(limit, 60),
            "api_key": self.env("SERPAPI_KEY"),
        }
        async with self.client() as c:
            r = await c.get(self.URL, params=params)
            r.raise_for_status()
            data = r.json()
        offers = []
        for item in data.get("shopping_results", [])[:limit]:
            price = item.get("extracted_price")
            if not price:
                continue
            offers.append(
                Offer(
                    title=item.get("title", "").strip(),
                    price=float(price),
                    regular_price=item.get("extracted_old_price"),
                    store=item.get("source") or "Unknown store",
                    url=item.get("product_link") or item.get("link") or "",
                    source=self.name,
                    rating=item.get("rating"),
                    reviews=item.get("reviews"),
                    image=item.get("thumbnail"),
                )
            )
        return offers

    async def search(self, query: str, limit: int = 20) -> list[Offer]:
        return await self._query(query, limit)

    async def new_releases(self, category: str, brand: str | None, days: int, limit: int = 20) -> list[Offer]:
        # Google Shopping has no release-date filter; a "new" query is the best approximation.
        # Best Buy (below) gives exact release dates when its key is set.
        return await self._query(f"new {brand or ''} {category}".replace("  ", " "), limit)
