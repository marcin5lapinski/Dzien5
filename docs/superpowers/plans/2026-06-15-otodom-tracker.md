# Otodom Tracker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować lokalną aplikację Flask, która scrape'uje oferty mieszkań z otodom.pl, zapisuje je do SQLite, wysyła nowe na Discord i pokazuje statystyki na dashboardzie w stylu Dzikiego Zachodu.

**Architecture:** Jeden serwer Flask serwuje API i frontend (single-page). Scraper wyciąga dane z `__NEXT_DATA__` JSON osadzonego w HTML otodom. Discord używa HTTP API bezpośrednio przez `requests` (bez gateway/intents — bot tylko wysyła).

**Tech Stack:** Python 3.10+ · Flask · requests · BeautifulSoup4 · sqlite3 (stdlib) · python-dotenv · pytest · Chart.js (CDN) · Google Fonts: Rye, Libre Baskerville (CDN)

---

## Mapa plików

| Plik | Odpowiedzialność |
|---|---|
| `config.py` | wczytuje `.env` → eksportuje `DISCORD_TOKEN`, `GUILD_ID`, `DB_PATH` |
| `database.py` | init SQLite, `save_listings()`, `mark_sent()`, `get_stats()` |
| `scraper.py` | `fetch_listings()` → URL budowanie + `_parse_listings()` → `__NEXT_DATA__` |
| `discord_bot.py` | `send_listing()` → Discord HTTP API, `_get_or_create_channel()` |
| `app.py` | Flask: `POST /api/fetch`, `GET /api/stats`, `GET /` |
| `templates/index.html` | Wild West frontend: formularz, filtry, KPI, Chart.js, tabela |
| `tests/test_database.py` | testy jednostkowe bazy (in-memory SQLite) |
| `tests/test_scraper.py` | testy parsera HTML (mock HTTP) |
| `tests/test_discord.py` | testy wysyłki Discord (mock HTTP) |
| `tests/test_app.py` | testy endpointów Flask (test client) |

---

## Task 1: Setup projektu

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`
- Create: `tests/__init__.py`

- [ ] **Krok 1: Utwórz strukturę katalogów**

```
mkdir tests
mkdir templates
```

- [ ] **Krok 2: Utwórz requirements.txt**

```
flask
requests
beautifulsoup4
python-dotenv
pytest
```

- [ ] **Krok 3: Zainstaluj zależności**

```bash
pip install -r requirements.txt
```

Oczekiwany output: `Successfully installed flask-... requests-... beautifulsoup4-... python-dotenv-... pytest-...`

- [ ] **Krok 4: Utwórz .env.example**

```
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
DB_PATH=listings.db
```

- [ ] **Krok 5: Utwórz .env (wypełniony danymi)**

Skopiuj `.env.example` do `.env` i wstaw prawdziwy token bota i Guild ID:

```
DISCORD_TOKEN=<twój token z Discord Developer Portal>
GUILD_ID=<ID twojego serwera Discord>
DB_PATH=listings.db
```

- [ ] **Krok 6: Utwórz config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "")
DB_PATH = os.getenv("DB_PATH", "listings.db")
```

- [ ] **Krok 7: Utwórz tests/__init__.py**

```python
```
(pusty plik)

- [ ] **Krok 8: Commit**

```bash
git init
git add requirements.txt .env.example config.py tests/__init__.py
git commit -m "feat: project setup — config and dependencies"
```

---

## Task 2: Warstwa bazy danych

**Files:**
- Create: `database.py`
- Create: `tests/test_database.py`

- [ ] **Krok 1: Napisz testy (najpierw czerwone)**

Utwórz `tests/test_database.py`:

```python
import pytest
import sqlite3
import database as db_module

SAMPLE = {
    "id": "abc123",
    "city": "wroclaw",
    "title": "3 pokoje, Śródmieście",
    "price": 750000.0,
    "area": 55.0,
    "price_per_m2": 13636.0,
    "url": "https://www.otodom.pl/pl/oferta/abc123",
}

@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()

def test_init_db_creates_table():
    with sqlite3.connect(db_module.DB_PATH) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    assert ("listings",) in tables

def test_save_listings_returns_new():
    new = db_module.save_listings([SAMPLE])
    assert len(new) == 1
    assert new[0]["id"] == "abc123"

def test_save_duplicate_not_returned():
    db_module.save_listings([SAMPLE])
    new = db_module.save_listings([SAMPLE])
    assert new == []

def test_get_stats_empty():
    stats = db_module.get_stats()
    assert stats["total"] == 0
    assert stats["avg_price"] == 0

def test_get_stats_basic():
    db_module.save_listings([SAMPLE])
    stats = db_module.get_stats()
    assert stats["total"] == 1
    assert stats["avg_price"] == 750000
    assert stats["avg_price_per_m2"] == 13636
    assert stats["avg_area"] == 55.0

def test_get_stats_filter_by_city():
    other = {**SAMPLE, "id": "xyz", "city": "krakow"}
    db_module.save_listings([SAMPLE, other])
    stats = db_module.get_stats(city="wroclaw")
    assert stats["total"] == 1

def test_get_stats_filter_price_max():
    cheap = {**SAMPLE, "id": "cheap", "price": 300000.0, "price_per_m2": 7500.0}
    db_module.save_listings([SAMPLE, cheap])
    stats = db_module.get_stats(price_max=500000)
    assert stats["total"] == 1

def test_get_stats_filter_area_min():
    small = {**SAMPLE, "id": "small", "area": 20.0, "price_per_m2": 20000.0}
    db_module.save_listings([SAMPLE, small])
    stats = db_module.get_stats(area_min=40)
    assert stats["total"] == 1

def test_mark_sent():
    db_module.save_listings([SAMPLE])
    db_module.mark_sent(["abc123"])
    with sqlite3.connect(db_module.DB_PATH) as conn:
        row = conn.execute(
            "SELECT sent_to_discord FROM listings WHERE id='abc123'"
        ).fetchone()
    assert row[0] == 1

def test_listings_in_stats():
    db_module.save_listings([SAMPLE])
    stats = db_module.get_stats()
    assert len(stats["listings"]) == 1
    assert stats["listings"][0]["title"] == "3 pokoje, Śródmieście"
```

- [ ] **Krok 2: Uruchom testy — upewnij się że FAIL**

```bash
pytest tests/test_database.py -v
```

Oczekiwany output: `ERROR` lub `ImportError` (database.py nie istnieje)

- [ ] **Krok 3: Utwórz database.py**

```python
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from config import DB_PATH


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                city TEXT NOT NULL,
                title TEXT,
                price REAL,
                area REAL,
                price_per_m2 REAL,
                url TEXT,
                fetched_at TEXT,
                sent_to_discord INTEGER DEFAULT 0
            )
        """)


def save_listings(listings: list) -> list:
    new = []
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        for listing in listings:
            row = {**listing, "fetched_at": now}
            cur = conn.execute(
                """INSERT OR IGNORE INTO listings
                   (id, city, title, price, area, price_per_m2, url, fetched_at)
                   VALUES (:id, :city, :title, :price, :area, :price_per_m2, :url, :fetched_at)""",
                row,
            )
            if cur.rowcount > 0:
                new.append(row)
    return new


def mark_sent(listing_ids: list):
    if not listing_ids:
        return
    with get_conn() as conn:
        conn.executemany(
            "UPDATE listings SET sent_to_discord = 1 WHERE id = ?",
            [(lid,) for lid in listing_ids],
        )


def get_stats(
    city: Optional[str] = None,
    price_max: Optional[float] = None,
    area_min: Optional[float] = None,
) -> dict:
    conditions, params = [], []
    if city:
        conditions.append("city = ?")
        params.append(city.lower())
    if price_max is not None:
        conditions.append("price <= ?")
        params.append(price_max)
    if area_min is not None:
        conditions.append("area >= ?")
        params.append(area_min)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM listings {where} ORDER BY fetched_at DESC", params
        ).fetchall()

    if not rows:
        return {
            "total": 0, "avg_price": 0, "avg_price_per_m2": 0, "avg_area": 0,
            "price_histogram": [], "area_histogram": [], "listings": [],
        }

    prices = [r["price"] for r in rows if r["price"]]
    areas = [r["area"] for r in rows if r["area"]]
    ppms = [r["price_per_m2"] for r in rows if r["price_per_m2"]]

    return {
        "total": len(rows),
        "avg_price": round(sum(prices) / len(prices)) if prices else 0,
        "avg_price_per_m2": round(sum(ppms) / len(ppms)) if ppms else 0,
        "avg_area": round(sum(areas) / len(areas), 1) if areas else 0,
        "price_histogram": _histogram(prices, 6),
        "area_histogram": _histogram(areas, 6),
        "listings": [dict(r) for r in rows],
    }


def _histogram(values: list, bins: int) -> list:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [[round(lo), len(values)]]
    step = (hi - lo) / bins
    result = []
    for i in range(bins):
        bucket_lo = lo + i * step
        bucket_hi = bucket_lo + step
        count = sum(1 for v in values if bucket_lo <= v < bucket_hi)
        result.append([round(bucket_lo), count])
    return result
```

- [ ] **Krok 4: Uruchom testy — upewnij się że PASS**

```bash
pytest tests/test_database.py -v
```

Oczekiwany output: `10 passed`

- [ ] **Krok 5: Commit**

```bash
git add database.py tests/test_database.py
git commit -m "feat: database layer — SQLite init, save, stats, dedup"
```

---

## Task 3: Scraper otodom

**Files:**
- Create: `scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Krok 1: Napisz testy (najpierw czerwone)**

Utwórz `tests/test_scraper.py`:

```python
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
```

- [ ] **Krok 2: Uruchom testy — upewnij się że FAIL**

```bash
pytest tests/test_scraper.py -v
```

Oczekiwany output: `ImportError` (scraper.py nie istnieje)

- [ ] **Krok 3: Utwórz scraper.py**

```python
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


def city_to_slug(city: str) -> str:
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
```

- [ ] **Krok 4: Uruchom testy — upewnij się że PASS**

```bash
pytest tests/test_scraper.py -v
```

Oczekiwany output: `11 passed`

- [ ] **Krok 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: otodom scraper — __NEXT_DATA__ parser + diacritic slug"
```

---

## Task 4: Discord integration

**Files:**
- Create: `discord_bot.py`
- Create: `tests/test_discord.py`

- [ ] **Krok 1: Napisz testy (najpierw czerwone)**

Utwórz `tests/test_discord.py`:

```python
from unittest.mock import patch, MagicMock, call
import discord_bot

LISTING = {
    "id": "abc123",
    "city": "wroclaw",
    "title": "3 pokoje, Śródmieście",
    "price": 750000.0,
    "area": 55.0,
    "price_per_m2": 13636.0,
    "url": "https://www.otodom.pl/pl/oferta/abc123",
}

def make_mock_get(channels):
    mock = MagicMock()
    mock.json.return_value = channels
    mock.raise_for_status = MagicMock()
    return mock

def make_mock_post(channel_id="999"):
    mock = MagicMock()
    mock.json.return_value = {"id": channel_id}
    mock.raise_for_status = MagicMock()
    return mock


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_uses_existing_channel(mock_get, mock_post):
    mock_get.return_value = make_mock_get([
        {"id": "111", "name": "wroclaw", "type": 0}
    ])
    mock_post.return_value = make_mock_post()
    result = discord_bot.send_listing(LISTING)
    assert result is True
    assert mock_post.call_count == 1
    assert "messages" in mock_post.call_args[0][0]


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_creates_channel_when_missing(mock_get, mock_post):
    mock_get.return_value = make_mock_get([])
    mock_post.return_value = make_mock_post("222")
    discord_bot.send_listing(LISTING)
    assert mock_post.call_count == 2
    first_url = mock_post.call_args_list[0][0][0]
    second_url = mock_post.call_args_list[1][0][0]
    assert "channels" in first_url and "messages" not in first_url
    assert "messages" in second_url


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_message_contains_price_and_area(mock_get, mock_post):
    mock_get.return_value = make_mock_get([
        {"id": "111", "name": "wroclaw", "type": 0}
    ])
    mock_post.return_value = make_mock_post()
    discord_bot.send_listing(LISTING)
    content = mock_post.call_args[1]["json"]["content"]
    assert "750" in content
    assert "55" in content
    assert "https://www.otodom.pl" in content


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_returns_false_on_error(mock_get, mock_post):
    mock_get.side_effect = Exception("Network error")
    result = discord_bot.send_listing(LISTING)
    assert result is False


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_channel_name_from_city(mock_get, mock_post):
    mock_get.return_value = make_mock_get([])
    mock_post.return_value = make_mock_post()
    listing_with_spaces = {**LISTING, "city": "nowy sacz"}
    discord_bot.send_listing(listing_with_spaces)
    create_call_json = mock_post.call_args_list[0][1]["json"]
    assert create_call_json["name"] == "nowy-sacz"
```

- [ ] **Krok 2: Uruchom testy — upewnij się że FAIL**

```bash
pytest tests/test_discord.py -v
```

Oczekiwany output: `ImportError` (discord_bot.py nie istnieje)

- [ ] **Krok 3: Utwórz discord_bot.py**

```python
import requests
from config import DISCORD_TOKEN, GUILD_ID

BASE = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json",
}


def _get_or_create_channel(city: str) -> str:
    channel_name = city.lower().replace(" ", "-")
    resp = requests.get(f"{BASE}/guilds/{GUILD_ID}/channels", headers=HEADERS)
    resp.raise_for_status()
    for ch in resp.json():
        if ch.get("name") == channel_name and ch.get("type") == 0:
            return ch["id"]
    resp = requests.post(
        f"{BASE}/guilds/{GUILD_ID}/channels",
        headers=HEADERS,
        json={"name": channel_name, "type": 0},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def send_listing(listing: dict) -> bool:
    try:
        channel_id = _get_or_create_channel(listing["city"])
        price_str = f"{int(listing['price']):,}".replace(",", " ") if listing.get("price") else "?"
        area_str = f"{listing['area']:.0f}" if listing.get("area") else "?"
        ppm2_str = f"{int(listing['price_per_m2']):,}".replace(",", " ") if listing.get("price_per_m2") else "?"
        city_display = listing["city"].replace("-", " ").title()
        content = (
            f"🏠 **Nowe ogłoszenie — {city_display}**\n"
            f"📍 {listing['title']}\n"
            f"💰 {price_str} zł  |  📐 {area_str} m²  |  📊 {ppm2_str} zł/m²\n"
            f"🔗 {listing['url']}"
        )
        requests.post(
            f"{BASE}/channels/{channel_id}/messages",
            headers=HEADERS,
            json={"content": content},
        )
        return True
    except Exception:
        return False
```

- [ ] **Krok 4: Uruchom testy — upewnij się że PASS**

```bash
pytest tests/test_discord.py -v
```

Oczekiwany output: `5 passed`

- [ ] **Krok 5: Commit**

```bash
git add discord_bot.py tests/test_discord.py
git commit -m "feat: discord integration — HTTP API, auto-create channel"
```

---

## Task 5: Flask API

**Files:**
- Create: `app.py`
- Create: `tests/test_app.py`

- [ ] **Krok 1: Napisz testy (najpierw czerwone)**

Utwórz `tests/test_app.py`:

```python
import pytest
from unittest.mock import patch
import database as db_module

LISTING = {
    "id": "1",
    "city": "wroclaw",
    "title": "Test",
    "price": 500000.0,
    "area": 40.0,
    "price_per_m2": 12500.0,
    "url": "https://otodom.pl/pl/oferta/1",
}

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"html" in resp.data.lower()


def test_stats_empty_initially(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 0


@patch("app.send_listing", return_value=True)
@patch("app.fetch_listings", return_value=[LISTING])
def test_fetch_returns_counts(mock_scrape, mock_discord, client):
    resp = client.post(
        "/api/fetch",
        json={"city": "Wrocław", "voivodeship": "dolnośląskie"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fetched"] == 1
    assert data["new"] == 1
    assert data["discord_sent"] == 1


@patch("app.send_listing", return_value=True)
@patch("app.fetch_listings", return_value=[LISTING])
def test_second_fetch_no_duplicates(mock_scrape, mock_discord, client):
    client.post("/api/fetch", json={"city": "Wrocław", "voivodeship": "dolnośląskie"}, content_type="application/json")
    resp = client.post("/api/fetch", json={"city": "Wrocław", "voivodeship": "dolnośląskie"}, content_type="application/json")
    data = resp.get_json()
    assert data["new"] == 0
    assert data["discord_sent"] == 0


def test_fetch_missing_city_returns_400(client):
    resp = client.post(
        "/api/fetch",
        json={"voivodeship": "dolnośląskie"},
        content_type="application/json",
    )
    assert resp.status_code == 400


@patch("app.send_listing", return_value=True)
@patch("app.fetch_listings", return_value=[LISTING])
def test_stats_updates_after_fetch(mock_scrape, mock_discord, client):
    client.post("/api/fetch", json={"city": "Wrocław", "voivodeship": "dolnośląskie"}, content_type="application/json")
    resp = client.get("/api/stats")
    data = resp.get_json()
    assert data["total"] == 1
    assert data["avg_price"] == 500000
```

- [ ] **Krok 2: Uruchom testy — upewnij się że FAIL**

```bash
pytest tests/test_app.py -v
```

Oczekiwany output: `ImportError` (app.py nie istnieje)

- [ ] **Krok 3: Utwórz app.py**

```python
from flask import Flask, request, jsonify, render_template
from database import init_db, save_listings, mark_sent, get_stats
from scraper import fetch_listings
from discord_bot import send_listing

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip()
    voivodeship = (data.get("voivodeship") or "").strip()
    if not city or not voivodeship:
        return jsonify({"error": "city and voivodeship required"}), 400

    listings = fetch_listings(city, voivodeship)
    new_listings = save_listings(listings)

    discord_sent = 0
    sent_ids = []
    for listing in new_listings:
        if send_listing(listing):
            discord_sent += 1
            sent_ids.append(listing["id"])

    mark_sent(sent_ids)

    return jsonify({
        "fetched": len(listings),
        "new": len(new_listings),
        "discord_sent": discord_sent,
    })


@app.route("/api/stats")
def api_stats():
    city = request.args.get("city") or None
    price_max = request.args.get("price_max", type=float)
    area_min = request.args.get("area_min", type=float)
    return jsonify(get_stats(city, price_max, area_min))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
```

- [ ] **Krok 4: Uruchom testy — upewnij się że PASS**

```bash
pytest tests/test_app.py -v
```

Oczekiwany output: `6 passed`

- [ ] **Krok 5: Uruchom wszystkie testy**

```bash
pytest -v
```

Oczekiwany output: wszystkie testy z task 2-5 zielone (łącznie ~32 passed)

- [ ] **Krok 6: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: Flask API — /api/fetch, /api/stats, dedup + discord flow"
```

---

## Task 6: Wild West Frontend

**Files:**
- Create: `templates/index.html`

Brak testów jednostkowych — testujemy ręcznie przez uruchomienie aplikacji.

- [ ] **Krok 1: Utwórz templates/index.html**

```html
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Otodom Tracker — Dziki Zachód</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rye&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --sand: #f2e8c9; --dark: #2b1a0e; --brown: #5c3317;
    --amber: #c17f24; --red: #8b2020; --leather: #8b5e3c;
    --parchment: #ede0c0; --ink: #1a0f00;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--dark);
    background-image: repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.15) 2px,rgba(0,0,0,.15) 3px),
      radial-gradient(ellipse at 50% 0%,#3d2510 0%,#2b1a0e 60%);
    font-family: 'Libre Baskerville', Georgia, serif;
    color: var(--sand); min-height: 100vh; padding-bottom: 48px;
  }
  .header { background: var(--brown); border-bottom: 4px solid var(--amber); }
  .header-inner { max-width: 960px; margin: 0 auto; padding: 20px 24px 16px;
    display: flex; align-items: center; justify-content: space-between; }
  .logo { font-family: 'Rye', cursive; font-size: 1.8rem; color: var(--amber);
    text-shadow: 2px 2px 0 var(--dark); letter-spacing: 2px; }
  .logo small { color: var(--sand); font-size: 0.75rem; display: block;
    letter-spacing: 4px; text-transform: uppercase; font-family: 'Libre Baskerville', serif; }
  .wrap { max-width: 960px; margin: 0 auto; padding: 24px; }

  /* POSTER */
  .poster { background: var(--parchment); border: 6px solid var(--brown); border-radius: 4px;
    box-shadow: 0 8px 32px rgba(0,0,0,.5),inset 0 0 40px rgba(139,94,60,.2);
    position: relative; padding: 28px 32px 24px; color: var(--ink); margin-bottom: 24px; }
  .poster::before { content: '✦ WANTED ✦'; font-family: 'Rye',cursive; font-size: 2rem;
    color: var(--red); text-align: center; display: block; letter-spacing: 6px; margin-bottom: 4px; }
  .poster::after { content: ''; position: absolute; top: 8px; left: 8px; right: 8px; bottom: 8px;
    border: 2px solid var(--amber); border-radius: 2px; pointer-events: none; }
  .poster-sub { text-align: center; font-size: 0.78rem; letter-spacing: 3px;
    text-transform: uppercase; color: var(--brown); margin-bottom: 20px; font-style: italic; }
  .poster-fields { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; justify-content: center; }
  .field-group label { display: flex; flex-direction: column; gap: 4px;
    font-size: 0.68rem; letter-spacing: 2px; text-transform: uppercase; color: var(--brown); font-weight: 700; }
  .field-group input, .field-group select {
    background: #fff8e8; border: 2px solid var(--brown); border-radius: 2px;
    padding: 8px 12px; font-family: 'Libre Baskerville',serif; font-size: 0.95rem;
    color: var(--ink); min-width: 180px; }
  .btn-wanted { background: var(--red); color: var(--sand); border: 3px solid var(--dark);
    border-radius: 2px; padding: 10px 24px; font-family: 'Rye',cursive; font-size: 1rem;
    letter-spacing: 2px; cursor: pointer; box-shadow: 3px 3px 0 var(--dark);
    transition: transform .1s, box-shadow .1s; }
  .btn-wanted:hover { transform: translate(1px,1px); box-shadow: 2px 2px 0 var(--dark); }
  .btn-wanted:disabled { opacity: .6; cursor: not-allowed; }
  #status { display: none; margin-top: 16px; background: var(--dark); color: var(--amber);
    border: 2px solid var(--amber); border-radius: 2px; padding: 8px 16px;
    font-size: 0.85rem; letter-spacing: 1px; text-align: center; }

  /* SALOON */
  .saloon { background: var(--brown); border: 4px solid var(--amber); border-radius: 4px;
    padding: 16px 20px; margin-bottom: 24px; }
  .saloon-title { font-family: 'Rye',cursive; font-size: 0.95rem; color: var(--amber);
    letter-spacing: 3px; margin-bottom: 12px; }
  .saloon-fields { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
  .saloon-fields label { display: flex; flex-direction: column; gap: 4px;
    font-size: 0.65rem; letter-spacing: 2px; text-transform: uppercase; color: var(--sand); }
  .saloon-fields input, .saloon-fields select { background: var(--dark); border: 2px solid var(--amber);
    border-radius: 2px; padding: 6px 10px; font-family: 'Libre Baskerville',serif;
    font-size: 0.85rem; color: var(--sand); min-width: 140px; }
  .btn-filter { background: var(--amber); color: var(--dark); border: 2px solid var(--dark);
    border-radius: 2px; padding: 8px 18px; font-family: 'Rye',cursive; font-size: 0.85rem;
    cursor: pointer; box-shadow: 2px 2px 0 var(--dark); }

  /* KPI */
  .badges { display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 24px; }
  .badge { background: var(--parchment); border: 4px solid var(--brown); border-radius: 4px;
    padding: 14px 20px; min-width: 120px; text-align: center;
    box-shadow: 4px 4px 0 var(--dark); position: relative; }
  .badge::before { content: '★'; position: absolute; top: -12px; left: 50%;
    transform: translateX(-50%); color: var(--amber); background: var(--brown);
    width: 22px; height: 22px; display: grid; place-items: center;
    border-radius: 50%; font-size: 0.7rem; border: 2px solid var(--amber); }
  .badge .v { font-family: 'Rye',cursive; font-size: 1.4rem; color: var(--red); display: block; }
  .badge .l { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 2px;
    color: var(--brown); font-weight: 700; }

  /* CHARTS */
  .charts { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 24px; }
  .chart-box { background: var(--parchment); border: 4px solid var(--brown); border-radius: 4px;
    padding: 16px; flex: 1; min-width: 220px; box-shadow: 4px 4px 0 var(--dark); }
  .chart-title { font-family: 'Rye',cursive; font-size: 0.82rem; color: var(--red);
    letter-spacing: 2px; margin-bottom: 10px; }
  canvas { max-height: 160px; }

  /* TABLE */
  .board { background: var(--parchment); border: 4px solid var(--brown); border-radius: 4px;
    box-shadow: 4px 4px 0 var(--dark); overflow: hidden; }
  .board-header { background: var(--brown); padding: 12px 20px; font-family: 'Rye',cursive;
    font-size: 0.95rem; color: var(--amber); letter-spacing: 3px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; color: var(--ink); }
  thead tr { background: rgba(139,94,60,.2); }
  th { padding: 8px 14px; text-align: left; font-size: 0.68rem; text-transform: uppercase;
    letter-spacing: 2px; color: var(--brown); border-bottom: 2px solid var(--brown); }
  td { padding: 8px 14px; border-bottom: 1px solid rgba(92,51,23,.2); }
  tr:last-child td { border-bottom: none; }
  .price-cell { color: var(--red); font-weight: 700; }
  a { color: var(--brown); }
  @media(max-width:600px){ .poster-fields, .saloon-fields { flex-direction: column; } }
</style>
</head>
<body>

<header class="header">
  <div class="header-inner">
    <div class="logo">Otodom Tracker <small>★ Dziki Zachód Nieruchomości ★</small></div>
    <span style="font-size:1.8rem;">🤠</span>
  </div>
</header>

<div class="wrap">

  <div class="poster">
    <div class="poster-sub">Szukamy najnowszych ofert w okolicy</div>
    <div class="poster-fields">
      <div class="field-group">
        <label>Miasto
          <input id="city" type="text" placeholder="np. Wrocław" value="Wrocław">
        </label>
      </div>
      <div class="field-group">
        <label>Województwo
          <select id="voivodeship">
            <option>dolnośląskie</option>
            <option>kujawsko-pomorskie</option>
            <option>lubelskie</option>
            <option>lubuskie</option>
            <option>łódzkie</option>
            <option>małopolskie</option>
            <option>mazowieckie</option>
            <option>opolskie</option>
            <option>podkarpackie</option>
            <option>podlaskie</option>
            <option>pomorskie</option>
            <option>śląskie</option>
            <option>świętokrzyskie</option>
            <option>warmińsko-mazurskie</option>
            <option>wielkopolskie</option>
            <option>zachodniopomorskie</option>
          </select>
        </label>
      </div>
      <button class="btn-wanted" id="btn-fetch" onclick="doFetch()">🔫 Szukaj!</button>
    </div>
    <div id="status"></div>
  </div>

  <div class="saloon">
    <div class="saloon-title">⚙ Zawęź Poszukiwania</div>
    <div class="saloon-fields">
      <label>Miasto (filtr)
        <select id="f-city"><option value="">Wszystkie</option></select>
      </label>
      <label>Cena max (zł)
        <input id="f-price" type="number" placeholder="bez limitu">
      </label>
      <label>Pow. min (m²)
        <input id="f-area" type="number" placeholder="0">
      </label>
      <button class="btn-filter" onclick="loadStats()">Filtruj</button>
    </div>
  </div>

  <div class="badges">
    <div class="badge"><span class="v" id="kpi-total">—</span><span class="l">Oferty</span></div>
    <div class="badge"><span class="v" id="kpi-price">—</span><span class="l">Śr. Cena</span></div>
    <div class="badge"><span class="v" id="kpi-ppm2">—</span><span class="l">Cena/m²</span></div>
    <div class="badge"><span class="v" id="kpi-area">—</span><span class="l">Śr. Pow.</span></div>
  </div>

  <div class="charts">
    <div class="chart-box">
      <div class="chart-title">Bounty — Rozkład Cen</div>
      <canvas id="chart-price"></canvas>
    </div>
    <div class="chart-box">
      <div class="chart-title">Rewir — Rozkład Metraży</div>
      <canvas id="chart-area"></canvas>
    </div>
  </div>

  <div class="board">
    <div class="board-header">📋 Tablica Ogłoszeń Szeryfatu</div>
    <table>
      <thead><tr>
        <th>Tytuł</th><th>Miasto</th><th>Cena (zł)</th><th>m²</th><th>zł/m²</th><th>Link</th>
      </tr></thead>
      <tbody id="listings-body">
        <tr><td colspan="6" style="text-align:center;color:var(--brown);padding:20px;">
          Naciśnij 🔫 Szukaj aby pobrać oferty
        </td></tr>
      </tbody>
    </table>
  </div>

</div>

<script>
let priceChart = null, areaChart = null;
const CHART_OPTS = {
  responsive: true, maintainAspectRatio: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: '#5c3317', font: { size: 10 } }, grid: { color: 'rgba(92,51,23,.15)' } },
    y: { ticks: { color: '#5c3317', font: { size: 10 } }, grid: { color: 'rgba(92,51,23,.15)' } },
  }
};

function fmt(n) {
  if (n == null) return '?';
  return Math.round(n).toLocaleString('pl-PL');
}

async function doFetch() {
  const btn = document.getElementById('btn-fetch');
  const status = document.getElementById('status');
  btn.disabled = true;
  btn.textContent = '⏳ Ładuję...';
  status.style.display = 'none';
  try {
    const resp = await fetch('/api/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        city: document.getElementById('city').value,
        voivodeship: document.getElementById('voivodeship').value,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Błąd serwera');
    status.textContent = `✅ Pojmano ${data.fetched} ofert · ${data.new} nowe · wysłano szeryfa na Discord: ${data.discord_sent}`;
    status.style.display = 'block';
    await loadStats();
  } catch (e) {
    status.textContent = '❌ Błąd: ' + e.message;
    status.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = '🔫 Szukaj!';
  }
}

async function loadStats() {
  const params = new URLSearchParams();
  const city = document.getElementById('f-city').value;
  const price = document.getElementById('f-price').value;
  const area = document.getElementById('f-area').value;
  if (city) params.set('city', city);
  if (price) params.set('price_max', price);
  if (area) params.set('area_min', area);

  const resp = await fetch('/api/stats?' + params);
  const data = await resp.json();

  document.getElementById('kpi-total').textContent = data.total;
  document.getElementById('kpi-price').textContent = data.avg_price ? fmt(data.avg_price) + ' zł' : '—';
  document.getElementById('kpi-ppm2').textContent = data.avg_price_per_m2 ? fmt(data.avg_price_per_m2) : '—';
  document.getElementById('kpi-area').textContent = data.avg_area ? data.avg_area + ' m²' : '—';

  updateChart('chart-price', priceChart, data.price_histogram, (c) => priceChart = c, '#8b2020', '#c17f24');
  updateChart('chart-area', areaChart, data.area_histogram, (c) => areaChart = c, '#5c3317', '#8b5e3c');

  updateTable(data.listings || []);
  updateCityFilter(data.listings || []);
}

function updateChart(id, existing, histogram, setter, color1, color2) {
  const labels = histogram.map(([v]) => fmt(v));
  const values = histogram.map(([, c]) => c);
  if (existing) {
    existing.data.labels = labels;
    existing.data.datasets[0].data = values;
    existing.update();
  } else {
    const ctx = document.getElementById(id).getContext('2d');
    setter(new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: color1, borderColor: color2, borderWidth: 2 }],
      },
      options: CHART_OPTS,
    }));
  }
}

function updateTable(listings) {
  const tbody = document.getElementById('listings-body');
  if (!listings.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--brown);padding:20px;">Brak ofert</td></tr>';
    return;
  }
  tbody.innerHTML = listings.map(l => `
    <tr>
      <td>${l.title || '—'}</td>
      <td>${(l.city || '').replace('-',' ')}</td>
      <td class="price-cell">${l.price ? fmt(l.price) : '—'}</td>
      <td>${l.area ? l.area.toFixed(0) : '—'}</td>
      <td>${l.price_per_m2 ? fmt(l.price_per_m2) : '—'}</td>
      <td><a href="${l.url}" target="_blank">otodom →</a></td>
    </tr>
  `).join('');
}

function updateCityFilter(listings) {
  const sel = document.getElementById('f-city');
  const current = sel.value;
  const cities = [...new Set(listings.map(l => l.city).filter(Boolean))].sort();
  sel.innerHTML = '<option value="">Wszystkie</option>' +
    cities.map(c => `<option value="${c}" ${c === current ? 'selected' : ''}>${c}</option>`).join('');
}

loadStats();
</script>
</body>
</html>
```

- [ ] **Krok 2: Uruchom aplikację**

```bash
python app.py
```

Oczekiwany output:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

- [ ] **Krok 3: Ręczne testy w przeglądarce**

Otwórz http://localhost:5000 i sprawdź:
- [ ] Strona ładuje się ze stylem Wild West i czcionką Rye
- [ ] Wpisz miasto + województwo, kliknij "🔫 Szukaj!" — pojawia się komunikat statusu
- [ ] KPI (Oferty, Śr. Cena, Cena/m², Śr. Pow.) wypełniają się wartościami
- [ ] Oba histogramy Chart.js rysują słupki
- [ ] Tabela pokazuje oferty z linkami do otodom
- [ ] Filtr po mieście zawęża dane w KPI, wykresach i tabeli
- [ ] Drugie kliknięcie "Szukaj" dla tego samego miasta pokazuje `0 nowych`
- [ ] Sprawdź kanał Discord — pojawiły się wiadomości o nowych ofertach

- [ ] **Krok 4: Commit końcowy**

```bash
git add templates/index.html app.py
git commit -m "feat: Wild West frontend — form, KPI, Chart.js, listings table"
```

---

## Weryfikacja końcowa

```bash
pytest -v
```

Oczekiwany output: wszystkie testy zielone (~32 passed, 0 failed)
