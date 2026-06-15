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
