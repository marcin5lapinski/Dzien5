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
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 0


@patch("app.send_listing", return_value=True)
@patch("app.fetch_listings", return_value=[LISTING])
def test_fetch_returns_counts(mock_scrape, mock_discord, client):
    resp = client.post(
        "/fetch",
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
    client.post("/fetch", json={"city": "Wrocław", "voivodeship": "dolnośląskie"}, content_type="application/json")
    resp = client.post("/fetch", json={"city": "Wrocław", "voivodeship": "dolnośląskie"}, content_type="application/json")
    data = resp.get_json()
    assert data["new"] == 0
    assert data["discord_sent"] == 0


def test_fetch_missing_city_returns_400(client):
    resp = client.post(
        "/fetch",
        json={"voivodeship": "dolnośląskie"},
        content_type="application/json",
    )
    assert resp.status_code == 400


@patch("app.send_listing", return_value=True)
@patch("app.fetch_listings", return_value=[LISTING])
def test_stats_updates_after_fetch(mock_scrape, mock_discord, client):
    client.post("/fetch", json={"city": "Wrocław", "voivodeship": "dolnośląskie"}, content_type="application/json")
    resp = client.get("/stats")
    data = resp.get_json()
    assert data["total"] == 1
    assert data["avg_price"] == 500000
