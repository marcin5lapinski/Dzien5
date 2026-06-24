CREATE TABLE IF NOT EXISTS listing_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tags_listing ON listing_tags(listing_id);
