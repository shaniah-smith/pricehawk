"""Provider interface. Each data source implements search, and optionally new_releases."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

import httpx

from ..models import Offer

USER_AGENT = "PriceHawk/0.1 (+https://github.com/)"


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def enabled(self) -> bool:
        """True when this provider has what it needs (API keys etc.)."""

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Offer]:
        ...

    async def new_releases(self, category: str, brand: str | None, days: int, limit: int = 20) -> list[Offer]:
        return []

    @staticmethod
    def client() -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=20, headers={"User-Agent": USER_AGENT}, follow_redirects=True)

    @staticmethod
    def env(key: str) -> str | None:
        v = os.environ.get(key, "").strip()
        return v or None

    @staticmethod
    def switch(key: str) -> bool:
        """On/off setting that defaults to on; 0, false or no turns it off."""
        return os.environ.get(key, "").strip().lower() not in ("0", "false", "no")
