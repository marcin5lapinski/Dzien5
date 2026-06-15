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
