import pytest
import sqlite3
from datetime import datetime, timezone
import database as db_module

SAMPLE_LISTING = {
    "id": "abc123",
    "city": "wroclaw",
    "title": "3 pokoje",
    "price": 750000.0,
    "area": 55.0,
    "price_per_m2": 13636.0,
    "url": "https://www.otodom.pl/pl/oferta/abc123",
}

SAMPLE_RATES = [
    {"currency_code": "USD", "currency_name": "dolar", "rate": 4.08, "date": "2025-01-02", "fetched_at": "2025-01-02T10:00:00+00:00"},
    {"currency_code": "EUR", "currency_name": "euro", "rate": 4.27, "date": "2025-01-02", "fetched_at": "2025-01-02T10:00:00+00:00"},
    {"currency_code": "USD", "currency_name": "dolar", "rate": 4.10, "date": "2025-01-03", "fetched_at": "2025-01-03T10:00:00+00:00"},
]


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()
    # Apply migrations inline for tests
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS currency_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency_code TEXT NOT NULL, currency_name TEXT,
            rate REAL NOT NULL, date TEXT NOT NULL, fetched_at TEXT NOT NULL,
            UNIQUE(currency_code, date)
        );
        CREATE TABLE IF NOT EXISTS listing_price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL, price REAL, price_per_m2 REAL, recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS listing_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL, session_id TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS listing_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL, session_id TEXT NOT NULL,
            tag TEXT NOT NULL, created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def test_save_currency_rates_returns_count():
    count = db_module.save_currency_rates(SAMPLE_RATES)
    assert count == 3


def test_save_currency_rates_deduplicates():
    db_module.save_currency_rates(SAMPLE_RATES)
    count = db_module.save_currency_rates(SAMPLE_RATES)
    assert count == 0


def test_get_latest_rates_returns_most_recent():
    db_module.save_currency_rates(SAMPLE_RATES)
    rates = db_module.get_latest_rates()
    assert "USD" in rates
    assert rates["USD"]["rate"] == 4.10  # 2025-01-03 is newer
    assert rates["USD"]["date"] == "2025-01-03"


def test_get_listing_returns_dict():
    db_module.save_listings([SAMPLE_LISTING])
    listing = db_module.get_listing("abc123")
    assert listing is not None
    assert listing["title"] == "3 pokoje"


def test_get_listing_returns_none_for_missing():
    result = db_module.get_listing("nonexistent")
    assert result is None


def test_record_price_if_changed_initial():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.record_price_if_changed("abc123", 750000.0, 13636.0)
    history = db_module.get_price_history("abc123")
    assert len(history) == 1
    assert history[0]["price"] == 750000.0


def test_record_price_if_changed_no_duplicate():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.record_price_if_changed("abc123", 750000.0, 13636.0)
    db_module.record_price_if_changed("abc123", 750000.0, 13636.0)
    history = db_module.get_price_history("abc123")
    assert len(history) == 1


def test_record_price_if_changed_tracks_change():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.record_price_if_changed("abc123", 750000.0, 13636.0)
    db_module.record_price_if_changed("abc123", 700000.0, 12727.0)
    history = db_module.get_price_history("abc123")
    assert len(history) == 2


def test_save_and_get_notes():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.save_note("abc123", "sess1", "świetna lokalizacja")
    notes = db_module.get_notes("abc123", "sess1")
    assert len(notes) == 1
    assert notes[0]["content"] == "świetna lokalizacja"
    assert "created_at" in notes[0]


def test_notes_isolated_by_session():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.save_note("abc123", "sess1", "moja notatka")
    notes_other = db_module.get_notes("abc123", "sess2")
    assert notes_other == []


def test_save_and_get_tags():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.save_tag("abc123", "sess1", "warto")
    tags = db_module.get_tags("abc123", "sess1")
    assert len(tags) == 1
    assert tags[0]["tag"] == "warto"


def test_search_listings_by_note():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.save_note("abc123", "sess1", "świetna lokalizacja blisko centrum")
    results = db_module.search_listings_by_note("centrum", "sess1")
    assert len(results) == 1
    assert results[0]["id"] == "abc123"


def test_search_listings_by_note_no_match():
    db_module.save_listings([SAMPLE_LISTING])
    db_module.save_note("abc123", "sess1", "dobra oferta")
    results = db_module.search_listings_by_note("centrum", "sess1")
    assert results == []
