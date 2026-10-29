"""Demo provider: realistic-looking SAMPLE data so you can try PriceHawk with no API keys.

Stores and brands are fictional and prices are generated from the query text, so the same
search always returns the same results. Never shown alongside real data unless
PRICEHAWK_DEMO=1 is set explicitly.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from ..models import Offer
from .base import Provider

STORES = ["DemoMart", "SampleShop", "Pixel Outlet", "BargainBay (demo)", "Northwind Goods"]
BRANDS = ["Aurora", "Vantis", "Nimbus", "Corvo", "Kestrel", "Lumen", "Halcyon", "Brio"]
MODELS = ["Pro", "Max", "Air", "Lite", "X2", "Studio", "Go", "Ultra"]


def _rng(*parts: str) -> random.Random:
    seed = hashlib.sha256("|".join(parts).lower().encode()).hexdigest()
    return random.Random(int(seed[:16], 16))


class DemoProvider(Provider):
    name = "demo"

    def enabled(self) -> bool:
        return True

    def _catalog(self, query: str, n: int) -> list[Offer]:
        r = _rng(query)
        base = r.choice([39, 79, 129, 199, 299, 449, 799])
        products = []
        for i in range(max(3, n // 3)):
            brand = r.choice(BRANDS)
            model = f"{brand} {query.title()} {r.choice(MODELS)}"
            list_price = round(base * r.uniform(0.7, 1.6), -1) - 0.01
            rating = round(r.uniform(3.4, 4.9), 1)
            reviews = int(r.expovariate(1 / 900))
            released = date.today() - timedelta(days=r.randint(5, 700))
            for store in r.sample(STORES, k=r.randint(2, 4)):
                price = round(list_price * r.uniform(0.62, 1.0), 2)
                products.append(
                    Offer(
                        title=model,
                        price=price,
                        regular_price=list_price,
                        store=store,
                        url=f"https://example.com/demo/{store.split()[0].lower()}/{i}",
                        source=self.name,
                        brand=brand,
                        rating=rating,
                        reviews=reviews,
                        release_date=released,
                    )
                )
        return products[:n]

    async def search(self, query: str, limit: int = 20) -> list[Offer]:
        return self._catalog(query, limit)

    async def new_releases(self, category: str, brand: str | None, days: int, limit: int = 20) -> list[Offer]:
        offers = self._catalog(f"{category} {brand or ''}".strip(), limit * 3)
        if brand:
            for o in offers:
                o.brand = brand.title()
                o.title = o.title.split(" ", 1)[1] if " " in o.title else o.title
                o.title = f"{brand.title()} {o.title}"
        cutoff = date.today() - timedelta(days=days)
        r = _rng("new", category, brand or "")
        for o in offers:  # make sure a few are actually recent
            if r.random() < 0.5:
                o.release_date = date.today() - timedelta(days=r.randint(1, days))
        return [o for o in offers if o.release_date and o.release_date >= cutoff][:limit]
