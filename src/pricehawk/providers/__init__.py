"""Data sources. Real providers switch on when their API keys are set."""

from __future__ import annotations

import os

from .base import Provider
from .demo import DemoProvider
from .serpapi import SerpApiProvider
from .serpapi_ebay import SerpApiEbayProvider
from .serpapi_walmart import SerpApiWalmartProvider

__all__ = ["Provider", "active_providers"]


def active_providers() -> list[Provider]:
    """Every real provider with keys set. Falls back to demo data when none are configured,
    or always includes it when PRICEHAWK_DEMO=1."""
    providers = (
        SerpApiProvider(),
        SerpApiWalmartProvider(),
        SerpApiEbayProvider(),
    )
    real: list[Provider] = [p for p in providers if p.enabled()]
    demo_flag = os.environ.get("PRICEHAWK_DEMO", "").strip().lower()
    if demo_flag in ("1", "true", "yes") or (not real and demo_flag not in ("0", "false", "no")):
        real.append(DemoProvider())
    return real
