CREATE TABLE IF NOT EXISTS listing_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT NOT NULL,
    price REAL,
    price_per_m2 REAL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ph_listing ON listing_price_history(listing_id);
