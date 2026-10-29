"""Provider parsing and switches, using sample responses (no network, no API keys)."""

import os

from pricehawk import server
from pricehawk.providers import active_providers
from pricehawk.providers.serpapi_ebay import SerpApiEbayProvider
from pricehawk.providers.serpapi_walmart import SerpApiWalmartProvider

WALMART = {
    "organic_results": [
        {
            "title": "Hub 7-in-1 ",
            "product_page_url": "https://www.walmart.com/ip/1",
            "rating": 4.4,
            "reviews": 812,
            "primary_offer": {"offer_price": 9.99, "was_price": 29.99, "min_price": 0},
        },
        {"title": "Sold out", "out_of_stock": True, "primary_offer": {"offer_price": 5.0}},
        {"title": "No price", "primary_offer": {"min_price": 0}},
    ]
}

EBAY = {
    "organic_results": [
        {
            "title": "AirPods Pro",
            "link": "https://www.ebay.com/itm/1",
            "condition": "Open Box",
            "price": {"raw": "$113.70", "extracted": 113.7},
            "old_price": {"raw": "$138.66", "extracted": 138.66, "discount": "18% off"},
        },
        {"title": "Coffee", "condition": "Brand New", "price": {"from": {"extracted": 24.6}, "to": {"extracted": 91.01}}},
        {"title": "Auction", "buying_format": "auction", "price": {"extracted": 1.0}},
    ]
}


def test_walmart_parse():
    offers = SerpApiWalmartProvider.parse(WALMART, 10)
    assert len(offers) == 1
    o = offers[0]
    assert (o.title, o.price, o.regular_price, o.store, o.source) == ("Hub 7-in-1", 9.99, 29.99, "Walmart", "walmart")
    assert round(o.discount, 2) == 0.67


def test_ebay_parse():
    offers = SerpApiEbayProvider.parse(EBAY, 10)
    assert [o.title for o in offers] == ["AirPods Pro (Open Box)", "Coffee"]
    assert offers[0].regular_price == 138.66
    assert offers[1].price == 24.6  # low end of a price range


def test_serpapi_key_turns_on_all_three(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "test")
    for key in ("PRICEHAWK_DEMO", "PRICEHAWK_WALMART", "PRICEHAWK_EBAY"):
        monkeypatch.delenv(key, raising=False)
    assert [p.name for p in active_providers()] == ["serpapi", "walmart", "ebay"]
    monkeypatch.setenv("PRICEHAWK_EBAY", "0")
    monkeypatch.setenv("PRICEHAWK_DEMO", "1")
    assert [p.name for p in active_providers()] == ["serpapi", "walmart", "demo"]


def test_load_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("# comment\nPH_TEST_A=from-file\nPH_TEST_B='quoted'\nPH_TEST_C=\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PH_TEST_B", "already-set")
    monkeypatch.delenv("PH_TEST_A", raising=False)
    monkeypatch.delenv("PH_TEST_C", raising=False)
    monkeypatch.delenv("PRICEHAWK_DOTENV", raising=False)
    server.load_dotenv()
    assert os.environ["PH_TEST_A"] == "from-file"
    assert os.environ["PH_TEST_B"] == "already-set"
    assert "PH_TEST_C" not in os.environ
    monkeypatch.delenv("PH_TEST_A")
