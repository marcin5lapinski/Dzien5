"""Run this script manually to apply all pending migrations."""
import os
import sqlite3
from pathlib import Path
from config import DB_PATH

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

def run():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    conn.commit()

    applied = {r[0] for r in conn.execute("SELECT filename FROM _migrations").fetchall()}
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    for path in sql_files:
        if path.name in applied:
            print(f"  SKIP {path.name}")
            continue
        print(f"  APPLY {path.name} ... ", end="")
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO _migrations (filename, applied_at) VALUES (?, datetime('now'))",
            (path.name,)
        )
        conn.commit()
        print("OK")

    conn.close()
    print("Done.")

if __name__ == "__main__":
    run()
