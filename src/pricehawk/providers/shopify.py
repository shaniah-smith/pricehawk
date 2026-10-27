"""Shopify agentic commerce (Universal Commerce Protocol over MCP).

Shopify's Catalog, Cart and Checkout services are themselves MCP servers that speak
JSON-RPC 2.0. PriceHawk calls them as a client:

- search_catalog / get_product  -> price comparison source + resolving a buyable variant
- create_checkout / get_checkout -> preparing an order and handing the buyer to checkout

Setup (https://shopify.dev/docs/agents/get-started/authentication):
  SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET  from the Catalog section of the Dev Dashboard
  SHOPIFY_CATALOG_URL                       the catalog URL shown in the Dev Dashboard
  SHOPIFY_AGENT_PROFILE                     your agent's UCP profile URL
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from ..models import Offer
from .base import Provider

TOKEN_URL = "https://api.shopify.com/auth/access_token"
DEFAULT_PROFILE = "https://shopify.dev/ucp/agent-profiles/examples/2026-08-25/valid-with-capabilities.json"


class ShopifyError(RuntimeError):
    pass


class ShopifyProvider(Provider):
    name = "shopify"

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires = 0.0

    def enabled(self) -> bool:
        return all(self.env(k) for k in ("SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET", "SHOPIFY_CATALOG_URL"))

    # ---- transport -------------------------------------------------------

    async def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        async with self.client() as c:
            r = await c.post(
                TOKEN_URL,
                json={
                    "client_id": self.env("SHOPIFY_CLIENT_ID"),
                    "client_secret": self.env("SHOPIFY_CLIENT_SECRET"),
                    "grant_type": "client_credentials",
                },
            )
            r.raise_for_status()
            data = r.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def _meta(self, idempotent: bool = False) -> dict[str, Any]:
        meta: dict[str, Any] = {"ucp-agent": {"profile": self.env("SHOPIFY_AGENT_PROFILE") or DEFAULT_PROFILE}}
        if idempotent:
            meta["idempotency-key"] = str(uuid.uuid4())
        return meta

    async def call(self, url: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        token = await self._access_token()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        async with self.client() as c:
            r = await c.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            data = r.json()
        if "error" in data:
            raise ShopifyError(data["error"].get("message", str(data["error"])))
        result = data.get("result", {})
        return result.get("structuredContent") or {}

    # ---- discovery -------------------------------------------------------

    async def search(self, query: str, limit: int = 20) -> list[Offer]:
        result = await self.call(
            self.env("SHOPIFY_CATALOG_URL") or "",
            "search_catalog",
            {
                "meta": self._meta(),
                "catalog": {"query": query, "filters": {"ships_to": {"country": (self.env("PRICEHAWK_COUNTRY") or "US").upper()}}},
            },
        )
        offers = []
        for p in result.get("products", [])[:limit]:
            low = (p.get("price_range") or {}).get("min") or {}
            if "amount" not in low:
                continue
            offers.append(
                Offer(
                    title=p.get("title", ""),
                    price=low["amount"] / 100,  # minor units
                    currency=low.get("currency", "USD"),
                    store="Shopify store",
                    url=p.get("url") or "",
                    source=self.name,
                    product_id=p.get("id"),
                )
            )
        return offers

    async def product(self, product_id: str) -> dict[str, Any]:
        result = await self.call(
            self.env("SHOPIFY_CATALOG_URL") or "",
            "get_product",
            {"meta": self._meta(), "catalog": {"id": product_id}, "id": product_id},
        )
        return result.get("product") or {}

    # ---- checkout ----------------------------------------------------------

    async def create_checkout(self, shop_domain: str, variant_id: str, quantity: int, email: str, currency: str) -> dict[str, Any]:
        return await self.call(
            f"https://{shop_domain}/api/ucp/mcp",
            "create_checkout",
            {
                "meta": self._meta(),
                "checkout": {
                    "currency": currency,
                    "line_items": [{"quantity": quantity, "item": {"id": variant_id}}],
                    "buyer": {"email": email},
                },
            },
        )

    async def get_checkout(self, shop_domain: str, checkout_id: str) -> dict[str, Any]:
        return await self.call(
            f"https://{shop_domain}/api/ucp/mcp", "get_checkout", {"meta": self._meta(), "id": checkout_id}
        )

    async def cancel_checkout(self, shop_domain: str, checkout_id: str) -> dict[str, Any]:
        return await self.call(
            f"https://{shop_domain}/api/ucp/mcp",
            "cancel_checkout",
            {"meta": self._meta(idempotent=True), "id": checkout_id},
        )
