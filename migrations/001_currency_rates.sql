CREATE TABLE IF NOT EXISTS currency_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency_code TEXT NOT NULL,
    currency_name TEXT,
    rate REAL NOT NULL,
    date TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(currency_code, date)
);
CREATE INDEX IF NOT EXISTS idx_cr_date ON currency_rates(date);
CREATE INDEX IF NOT EXISTS idx_cr_code ON currency_rates(currency_code);
