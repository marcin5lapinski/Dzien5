# -*- coding: utf-8 -*-
import json
from unittest.mock import patch, MagicMock
import scraper

ITEM = {
    "id": 99001,
    "title": "3 pokoje, Śródmieście",
    "totalPrice": {"value": 750000},
    "areaInSquareMeters": 55,
    "pricePerSquareMeter": {"value": 13636},
    "slug": "3-pokoje-srodmiescie-aa-bb",
}

NEXT_DATA = {
    "props": {
        "pageProps": {
            "data": {
                "searchAds": {
                    "items": [ITEM]
                }
            }
        }
    }
}

def html_with(data):
    payload = json.dumps(data)
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{payload}</script></body></html>'


def test_parse_extracts_id():
    results = scraper._parse_listings(html_with(NEXT_DATA), "wroclaw")
    assert results[0]["id"] == "99001"

def test_parse_extracts_price_and_area():
    results = scraper._parse_listings(html_with(NEXT_DATA), "wroclaw")
    assert results[0]["price"] == 750000.0
    assert results[0]["area"] == 55.0
    assert results[0]["price_per_m2"] == 13636.0

def test_parse_sets_city():
    results = scraper._parse_listings(html_with(NEXT_DATA), "wroclaw")
    assert results[0]["city"] == "wroclaw"

def test_parse_builds_url():
    results = scraper._parse_listings(html_with(NEXT_DATA), "wroclaw")
    assert results[0]["url"].startswith("https://www.otodom.pl/pl/oferta/")

def test_parse_returns_empty_when_no_script():
    results = scraper._parse_listings("<html><body></body></html>", "wroclaw")
    assert results == []

def test_parse_returns_empty_on_bad_json():
    html = '<html><body><script id="__NEXT_DATA__">{bad json</script></body></html>'
    results = scraper._parse_listings(html, "wroclaw")
    assert results == []

def test_parse_skips_item_without_price():
    item_no_price = {**ITEM, "id": 99002, "totalPrice": None}
    data = {"props": {"pageProps": {"data": {"searchAds": {"items": [item_no_price]}}}}}
    results = scraper._parse_listings(html_with(data), "wroclaw")
    assert len(results) == 1
    assert results[0]["price"] is None

def test_city_to_slug_removes_diacritics():
    assert scraper.city_to_slug("Wrocław") == "wroclaw"
    assert scraper.city_to_slug("Kraków") == "krakow"
    assert scraper.city_to_slug("Łódź") == "lodz"

def test_city_to_slug_replaces_spaces():
    assert scraper.city_to_slug("Nowy Sącz") == "nowy-sacz"

@patch("scraper.requests.get")
def test_fetch_returns_empty_on_exception(mock_get):
    mock_get.side_effect = Exception("timeout")
    result = scraper.fetch_listings("Wrocław", "dolnośląskie")
    assert result == []

@patch("scraper.requests.get")
def test_fetch_uses_voivodeship_slug_in_url(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = html_with(NEXT_DATA)
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp
    scraper.fetch_listings("Wrocław", "dolnośląskie")
    url = mock_get.call_args[0][0]
    assert "dolnoslaskie" in url
    assert "wroclaw" in url
