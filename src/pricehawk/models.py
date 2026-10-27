"""Shared data types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class Offer:
    """One product listing at one store, normalized across every data source."""

    title: str
    price: float
    store: str
    url: str
    source: str  # which provider found it (demo, serpapi, bestbuy, shopify)
    currency: str = "USD"
    brand: str | None = None
    rating: float | None = None  # 0-5
    reviews: int | None = None
    regular_price: float | None = None  # list price, used to compute discounts
    release_date: date | None = None
    image: str | None = None
    # Set when the listing can be bought through an agent checkout (Shopify UCP).
    product_id: str | None = None
    # Filled in by scoring.
    deal_score: float | None = None
    badges: list[str] = field(default_factory=list)

    @property
    def discount(self) -> float:
        """Fraction off list price (0.25 = 25% off)."""
        if self.regular_price and self.regular_price > self.price > 0:
            return 1 - self.price / self.regular_price
        return 0.0

    @property
    def buyable(self) -> bool:
        return self.source in ("shopify", "demo") and bool(self.product_id)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["release_date"] = self.release_date.isoformat() if self.release_date else None
        d["discount_pct"] = round(self.discount * 100)
        d["buyable"] = self.buyable
        return {k: v for k, v in d.items() if v not in (None, [], "")}
