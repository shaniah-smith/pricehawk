"""Best Buy Products API (https://developer.bestbuy.com). Free key; has exact release dates.

Needs BESTBUY_API_KEY.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import quote

from ..models import Offer
from .base import Provider

FIELDS = (
    "sku,name,salePrice,regularPrice,url,image,customerReviewAverage,"
    "customerReviewCount,releaseDate,manufacturer"
)


def _terms(text: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", text) if w]
    return "&".join(f"search={quote(w)}" for w in words[:6])


class BestBuyProvider(Provider):
    name = "bestbuy"
    BASE = "https://api.bestbuy.com/v1/products"

    def enabled(self) -> bool:
        return self.env("BESTBUY_API_KEY") is not None

    async def _get(self, filters: str, sort: str, limit: int) -> list[Offer]:
        url = f"{self.BASE}({filters})"
        params = {
            "apiKey": self.env("BESTBUY_API_KEY"),
            "format": "json",
            "show": FIELDS,
            "sort": sort,
            "pageSize": min(limit, 100),
        }
        async with self.client() as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        offers = []
        for p in data.get("products", []):
            released = None
            if p.get("releaseDate"):
                try:
                    released = date.fromisoformat(p["releaseDate"][:10])
                except ValueError:
                    pass
            offers.append(
                Offer(
                    title=p.get("name", ""),
                    price=float(p.get("salePrice") or 0),
                    regular_price=p.get("regularPrice"),
                    store="Best Buy",
                    url=p.get("url", ""),
                    source=self.name,
                    brand=p.get("manufacturer"),
                    rating=p.get("customerReviewAverage"),
                    reviews=p.get("customerReviewCount"),
                    release_date=released,
                    image=p.get("image"),
                )
            )
        return offers

    async def search(self, query: str, limit: int = 20) -> list[Offer]:
        return await self._get(_terms(query), "customerReviewCount.dsc", limit)

    async def new_releases(self, category: str, brand: str | None, days: int, limit: int = 20) -> list[Offer]:
        since = (date.today() - timedelta(days=days)).isoformat()
        filters = f"{_terms(category)}&releaseDate>={since}"
        if brand:
            filters += f"&manufacturer={quote(brand)}"
        return await self._get(filters, "releaseDate.dsc", limit)
