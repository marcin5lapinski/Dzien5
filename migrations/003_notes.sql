CREATE TABLE IF NOT EXISTS listing_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_listing ON listing_notes(listing_id);
CREATE INDEX IF NOT EXISTS idx_notes_session ON listing_notes(session_id);
