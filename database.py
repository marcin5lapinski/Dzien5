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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS currency_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_code TEXT NOT NULL,
                currency_name TEXT,
                rate REAL NOT NULL,
                date TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                UNIQUE(currency_code, date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listing_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                price REAL,
                price_per_m2 REAL,
                recorded_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listing_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listing_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_listings(listings: list) -> list:
    new = []
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        for listing in listings:
            row = {**listing, "fetched_at": now, "city": listing.get("city", "").lower()}
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

    prices = [r["price"] for r in rows if r["price"] is not None]
    areas = [r["area"] for r in rows if r["area"] is not None]
    ppms = [r["price_per_m2"] for r in rows if r["price_per_m2"] is not None]

    return {
        "total": len(rows),
        "avg_price": round(sum(prices) / len(prices)) if prices else 0,
        "avg_price_per_m2": round(sum(ppms) / len(ppms)) if ppms else 0,
        "avg_area": round(sum(areas) / len(areas), 1) if areas else 0,
        "price_histogram": _histogram(prices, 6),
        "area_histogram": _histogram(areas, 6),
        "listings": [dict(r) for r in rows],
    }


def get_unsent(city: str) -> list:
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM listings WHERE city = ? AND sent_to_discord = 0",
            (city.lower(),)
        ).fetchall()
    return [dict(r) for r in rows]


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
        if i < bins - 1:
            count = sum(1 for v in values if bucket_lo <= v < bucket_hi)
        else:
            count = sum(1 for v in values if bucket_lo <= v <= bucket_hi)
        result.append([round(bucket_lo), count])
    return result


def save_currency_rates(rates: list) -> int:
    """Insert rates, ignore duplicates (UNIQUE currency_code + date). Returns inserted count."""
    inserted = 0
    with get_conn() as conn:
        for r in rates:
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO currency_rates
                       (currency_code, currency_name, rate, date, fetched_at)
                       VALUES (:currency_code, :currency_name, :rate, :date, :fetched_at)""",
                    r,
                )
                inserted += cur.rowcount
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Skipping malformed rate dict: %s", e)
    return inserted


def get_latest_rates() -> dict:
    """Return {code: {rate, currency_name, date}} for the most recent date per currency."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT currency_code, currency_name, rate, date
            FROM currency_rates
            WHERE (currency_code, date) IN (
                SELECT currency_code, MAX(date) FROM currency_rates GROUP BY currency_code
            )
        """).fetchall()
    return {r["currency_code"]: dict(r) for r in rows}


def get_listing(listing_id: str) -> Optional[dict]:
    """Return a single listing by id, or None."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
    return dict(row) if row else None


def record_price_if_changed(listing_id: str, price: Optional[float], price_per_m2: Optional[float]):
    """Insert into price history only if price differs from the last recorded value."""
    with get_conn() as conn:
        last = conn.execute(
            "SELECT price FROM listing_price_history WHERE listing_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (listing_id,)
        ).fetchone()
        if last is None or last[0] != price:
            conn.execute(
                """INSERT INTO listing_price_history (listing_id, price, price_per_m2, recorded_at)
                   VALUES (?, ?, ?, ?)""",
                (listing_id, price, price_per_m2, datetime.now(timezone.utc).isoformat()),
            )


def get_price_history(listing_id: str) -> list:
    """Return price history for a listing, oldest first."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT price, price_per_m2, recorded_at FROM listing_price_history WHERE listing_id = ? ORDER BY recorded_at ASC",
            (listing_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def save_note(listing_id: str, session_id: str, content: str) -> dict:
    """Insert a note and return it."""
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO listing_notes (listing_id, session_id, content, created_at) VALUES (?, ?, ?, ?)",
            (listing_id, session_id, content, now),
        )
        return {"id": cur.lastrowid, "listing_id": listing_id, "content": content, "created_at": now}


def get_notes(listing_id: str, session_id: str) -> list:
    """Return all notes for a listing visible to this session."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, content, created_at FROM listing_notes WHERE listing_id = ? AND session_id = ? ORDER BY created_at ASC",
            (listing_id, session_id),
        ).fetchall()
    return [dict(r) for r in rows]


def save_tag(listing_id: str, session_id: str, tag: str) -> dict:
    """Insert a tag (idempotent per listing+session+tag) and return it."""
    tag = tag.strip()
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, created_at FROM listing_tags WHERE listing_id = ? AND session_id = ? AND tag = ?",
            (listing_id, session_id, tag),
        ).fetchone()
        if existing:
            return {"id": existing[0], "listing_id": listing_id, "tag": tag, "created_at": existing[1]}
        cur = conn.execute(
            "INSERT INTO listing_tags (listing_id, session_id, tag, created_at) VALUES (?, ?, ?, ?)",
            (listing_id, session_id, tag, now),
        )
        return {"id": cur.lastrowid, "listing_id": listing_id, "tag": tag, "created_at": now}


def get_tags(listing_id: str, session_id: str) -> list:
    """Return all tags for a listing visible to this session."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, tag, created_at FROM listing_tags WHERE listing_id = ? AND session_id = ? ORDER BY created_at ASC",
            (listing_id, session_id),
        ).fetchall()
    return [dict(r) for r in rows]


def search_listings_by_note(query: str, session_id: str) -> list:
    """Return listings that have notes matching `query` (LIKE search) for this session."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT DISTINCT l.* FROM listings l
               JOIN listing_notes n ON n.listing_id = l.id
               WHERE n.session_id = ? AND n.content LIKE ?
               ORDER BY l.fetched_at DESC""",
            (session_id, f"%{query}%"),
        ).fetchall()
    return [dict(r) for r in rows]
