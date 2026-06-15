# -*- coding: utf-8 -*-
import json
import unicodedata
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

VOIVODESHIP_SLUGS = {
    "dolnośląskie": "dolnoslaskie",
    "kujawsko-pomorskie": "kujawsko-pomorskie",
    "lubelskie": "lubelskie",
    "lubuskie": "lubuskie",
    "łódzkie": "lodzkie",
    "małopolskie": "malopolskie",
    "mazowieckie": "mazowieckie",
    "opolskie": "opolskie",
    "podkarpackie": "podkarpackie",
    "podlaskie": "podlaskie",
    "pomorskie": "pomorskie",
    "śląskie": "slaskie",
    "świętokrzyskie": "swietokrzyskie",
    "warmińsko-mazurskie": "warminsko-mazurskie",
    "wielkopolskie": "wielkopolskie",
    "zachodniopomorskie": "zachodniopomorskie",
}


# Characters that do not decompose via NFD and must be mapped explicitly
_EXTRA_MAP = str.maketrans({
    "Ł": "L",  # Ł
    "ł": "l",  # ł
})


def city_to_slug(city: str) -> str:
    city = city.translate(_EXTRA_MAP)
    city = city.lower().strip()
    city = unicodedata.normalize("NFD", city)
    city = "".join(c for c in city if unicodedata.category(c) != "Mn")
    return city.replace(" ", "-")


def fetch_listings(city: str, voivodeship: str, limit: int = 10) -> list:
    vslug = VOIVODESHIP_SLUGS.get(voivodeship.lower(), city_to_slug(voivodeship))
    cslug = city_to_slug(city)
    url = (
        f"https://www.otodom.pl/pl/oferty/sprzedaz/mieszkanie/{vslug}/{cslug}"
        f"?limit={limit}&by=LATEST&direction=DESC&viewType=listing"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_listings(resp.text, city_to_slug(city))
    except Exception:
        return []


def _parse_listings(html: str, city: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script:
        return []
    try:
        data = json.loads(script.string)
        items = data["props"]["pageProps"]["data"]["searchAds"]["items"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return []

    results = []
    for item in items:
        try:
            price_raw = (item.get("totalPrice") or {}).get("value")
            area_raw = item.get("areaInSquareMeters")
            ppm2_raw = (item.get("pricePerSquareMeter") or {}).get("value")
            if ppm2_raw is None and price_raw and area_raw:
                ppm2_raw = price_raw / area_raw
            results.append({
                "id": str(item["id"]),
                "city": city,
                "title": item.get("title", ""),
                "price": float(price_raw) if price_raw is not None else None,
                "area": float(area_raw) if area_raw is not None else None,
                "price_per_m2": float(ppm2_raw) if ppm2_raw is not None else None,
                "url": f"https://www.otodom.pl/pl/oferta/{item.get('slug', item['id'])}",
            })
        except (KeyError, TypeError):
            continue
    return results
